import csv
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Dict
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCE_DIR = os.path.join(BASE_DIR, "src", "data", "bookmaker_source")
OUTPUT_DIR = os.path.join(BASE_DIR, "src", "data", "historical_ready")
REVIEW_FILE = os.path.join(OUTPUT_DIR, "review_needed.csv")

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

SYNTHETIC_TOTAL_SPREAD = 0.02
PRICE_LOOKBACK_HOURS = 8
PRICE_FORWARD_MINUTES = 30
REQUEST_SLEEP_SECONDS = 0.15


def ensure_dirs() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def http_get_json(base_url: str, path: str, params: Optional[Dict] = None):
    url = f"{base_url}{path}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"

    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )

    with urlopen(req, timeout=30) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload)


def parse_list_field(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            loaded = json.loads(value)
            if isinstance(loaded, list):
                return loaded
        except Exception:
            pass
        return [x.strip() for x in value.split(",") if x.strip()]

    return []


def parse_timestamp(ts: str) -> datetime:
    if ts.endswith("Z"):
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.fromisoformat(ts + "+00:00")


def dt_to_unix(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def clipped_bid_ask(mid: float, total_spread: float):
    half = total_spread / 2.0
    best_bid = max(0.0, mid - half)
    best_ask = min(1.0, mid + half)

    if best_bid > best_ask:
        best_bid = mid
        best_ask = mid

    return best_bid, best_ask


def is_settlement_row(row: dict) -> bool:
    try:
        bid = float(row["best_bid"])
        ask = float(row["best_ask"])
        prob = float(row["bookmaker_prob"])
    except Exception:
        return False

    return (
        bid in (0.0, 1.0)
        and ask in (0.0, 1.0)
        and prob in (0.0, 1.0)
        and bid == ask == prob
    )


def parse_market_id(market_id: str):
    m = re.match(r"^(?P<league>[a-z0-9]+)_(?P<date>\d{8})_(?P<home>.+)_vs_(?P<away>.+)_home_win$", market_id)
    if not m:
        return None

    league = m.group("league")
    match_date = datetime.strptime(m.group("date"), "%Y%m%d").date()
    home = m.group("home").replace("_", " ").strip()
    away = m.group("away").replace("_", " ").strip()

    return {
        "league": league,
        "date": match_date,
        "home_team": home,
        "away_team": away,
    }


def normalize_text(s: str) -> str:
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    replacements = {
        "man united": "manchester united",
        "man utd": "manchester united",
        "man city": "manchester city",
        "spurs": "tottenham",
        "nottm forest": "nottingham forest",
        "ath madrid": "atletico madrid",
        "athletic bilbao": "athletic club",
        "inter milan": "inter",
        "ac milan": "milan",
        "psg": "paris saint germain",
        "bayern munich": "bayern",
    }

    for k, v in replacements.items():
        s = s.replace(k, v)

    return s


def token_set(team_name: str):
    txt = normalize_text(team_name)
    tokens = {t for t in txt.split() if len(t) >= 3}
    return tokens


def flatten_search_results(payload):
    results = []

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                results.append(item)
        return results

    if isinstance(payload, dict):
        for key in ("markets", "results", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        results.append(item)

        if payload.get("question") or payload.get("slug"):
            results.append(payload)

    return results


def search_polymarket_candidates(home_team: str, away_team: str):
    query = f"{home_team} {away_team}"

    payload = http_get_json(
        GAMMA_BASE,
        "/public-search",
        {
            "q": query,
            "keep_closed_markets": 1,
            "limit_per_type": 20,
            "search_profiles": "false",
            "search_tags": "false",
        },
    )

    time.sleep(REQUEST_SLEEP_SECONDS)
    return flatten_search_results(payload)


def get_market_detail_if_needed(candidate: dict):
    token_ids = parse_list_field(candidate.get("clobTokenIds")) or parse_list_field(candidate.get("tokenIds"))
    outcomes = parse_list_field(candidate.get("outcomes"))

    if token_ids and outcomes:
        return candidate

    market_id = candidate.get("id")
    if not market_id:
        return candidate

    try:
        detail = http_get_json(GAMMA_BASE, f"/markets/{market_id}")
        time.sleep(REQUEST_SLEEP_SECONDS)
        if isinstance(detail, dict):
            return detail
    except Exception:
        pass

    return candidate


def score_candidate(candidate: dict, home_team: str, away_team: str):
    question = candidate.get("question", "") or ""
    slug = candidate.get("slug", "") or ""
    text = normalize_text(f"{question} {slug}")

    home_tokens = token_set(home_team)
    away_tokens = token_set(away_team)

    home_hits = len([t for t in home_tokens if t in text])
    away_hits = len([t for t in away_tokens if t in text])

    score = home_hits + away_hits

    if home_hits > 0 and away_hits > 0:
        score += 5

    home_norm = normalize_text(home_team)
    away_norm = normalize_text(away_team)

    if home_norm in text and away_norm in text:
        if text.find(home_norm) < text.find(away_norm):
            score += 3

    bad_phrases = ["goals", "corners", "cards", "score", "first half", "shots", "assist", "player"]
    if any(bp in text for bp in bad_phrases):
        score -= 5

    return score


def choose_best_candidate(candidates, home_team: str, away_team: str):
    if not candidates:
        return None

    enriched = [get_market_detail_if_needed(c) for c in candidates]

    scored = []
    for c in enriched:
        scored.append((score_candidate(c, home_team, away_team), c))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored or scored[0][0] <= 0:
        return None

    return scored[0][1]


def extract_yes_token_id(market: dict):
    outcomes = parse_list_field(market.get("outcomes"))
    token_ids = parse_list_field(market.get("clobTokenIds")) or parse_list_field(market.get("tokenIds"))

    if not outcomes or not token_ids or len(outcomes) != len(token_ids):
        return None

    outcome_map = {}
    for outcome, token_id in zip(outcomes, token_ids):
        outcome_map[str(outcome).strip().lower()] = str(token_id)

    return outcome_map.get("yes")


def fetch_polymarket_midpoint(token_id: str, snapshot_dt: datetime):
    start_ts = dt_to_unix(snapshot_dt) - PRICE_LOOKBACK_HOURS * 3600
    end_ts = dt_to_unix(snapshot_dt) + PRICE_FORWARD_MINUTES * 60

    payload = http_get_json(
        CLOB_BASE,
        "/prices-history",
        {
            "market": token_id,
            "startTs": start_ts,
            "endTs": end_ts,
            "interval": "1h",
            "fidelity": 1,
        },
    )

    time.sleep(REQUEST_SLEEP_SECONDS)

    history = payload.get("history", [])
    if not history:
        return None

    best = None
    snapshot_unix = dt_to_unix(snapshot_dt)

    for point in history:
        try:
            t = int(point["t"])
            p = float(point["p"])
        except Exception:
            continue

        distance = abs(t - snapshot_unix)
        before_penalty = 0 if t <= snapshot_unix else 1000000
        rank = before_penalty + distance

        if best is None or rank < best[0]:
            best = (rank, p)

    if best is None:
        return None

    return best[1]


def process_source_file(input_path: str, output_path: str, review_rows):
    grouped = defaultdict(list)

    with open(input_path, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            market_id = row.get("market_id")
            if not market_id:
                review_rows.append({
                    "market_id": "",
                    "reason": "missing_market_id_column_or_value",
                    "candidate_question": "",
                    "candidate_slug": "",
                })
                continue
            grouped[market_id].append(row)

    output_rows = []
    market_ids = list(grouped.keys())
    total_markets = len(market_ids)

    print(f"  grouped into {total_markets} markets")

    for idx, market_id in enumerate(market_ids, start=1):
        if idx % 25 == 0 or idx == 1 or idx == total_markets:
            print(f"  processing market {idx}/{total_markets}: {market_id}")

        rows = grouped[market_id]

        try:
            parsed = parse_market_id(market_id)
            if parsed is None:
                review_rows.append({
                    "market_id": market_id,
                    "reason": "could_not_parse_market_id",
                    "candidate_question": "",
                    "candidate_slug": "",
                })
                continue

            pregame_rows = [r for r in rows if not is_settlement_row(r)]
            settlement_rows = [r for r in rows if is_settlement_row(r)]

            if not pregame_rows:
                review_rows.append({
                    "market_id": market_id,
                    "reason": "no_pregame_row_found",
                    "candidate_question": "",
                    "candidate_slug": "",
                })
                continue

            pregame_row = sorted(pregame_rows, key=lambda r: r["timestamp"])[0]
            snapshot_dt = parse_timestamp(pregame_row["timestamp"])

            candidates = search_polymarket_candidates(parsed["home_team"], parsed["away_team"])
            best_candidate = choose_best_candidate(candidates, parsed["home_team"], parsed["away_team"])

            if best_candidate is None:
                review_rows.append({
                    "market_id": market_id,
                    "reason": "no_polymarket_candidate_found",
                    "candidate_question": "",
                    "candidate_slug": "",
                })
                continue

            yes_token_id = extract_yes_token_id(best_candidate)
            if not yes_token_id:
                review_rows.append({
                    "market_id": market_id,
                    "reason": "no_yes_token_id_found",
                    "candidate_question": best_candidate.get("question", ""),
                    "candidate_slug": best_candidate.get("slug", ""),
                })
                continue

            midpoint = fetch_polymarket_midpoint(yes_token_id, snapshot_dt)
            if midpoint is None:
                review_rows.append({
                    "market_id": market_id,
                    "reason": "no_price_history_found",
                    "candidate_question": best_candidate.get("question", ""),
                    "candidate_slug": best_candidate.get("slug", ""),
                })
                continue

            best_bid, best_ask = clipped_bid_ask(midpoint, SYNTHETIC_TOTAL_SPREAD)

            output_rows.append({
                "timestamp": pregame_row["timestamp"],
                "market_id": pregame_row["market_id"],
                "best_bid": f"{best_bid:.6f}",
                "best_ask": f"{best_ask:.6f}",
                "bookmaker_prob": pregame_row["bookmaker_prob"],
            })

            for row in sorted(settlement_rows, key=lambda r: r["timestamp"]):
                output_rows.append({
                    "timestamp": row["timestamp"],
                    "market_id": row["market_id"],
                    "best_bid": row["best_bid"],
                    "best_ask": row["best_ask"],
                    "bookmaker_prob": row["bookmaker_prob"],
                })

        except Exception as e:
            review_rows.append({
                "market_id": market_id,
                "reason": f"exception_{type(e).__name__}",
                "candidate_question": "",
                "candidate_slug": "",
            })
            continue

    output_rows.sort(key=lambda r: (r["timestamp"], r["market_id"]))

    with open(output_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["timestamp", "market_id", "best_bid", "best_ask", "bookmaker_prob"],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"  wrote {len(output_rows)} rows to {output_path}")


def main():
    ensure_dirs()

    source_files = [
        f for f in os.listdir(SOURCE_DIR)
        if f.endswith(".csv")
    ]

    if not source_files:
        raise ValueError(f"No source CSV files found in {SOURCE_DIR}")

    review_rows = []

    print(f"Found {len(source_files)} source files")
    for filename in source_files:
        input_path = os.path.join(SOURCE_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename)

        print(f"Processing {filename} ...")
        process_source_file(input_path, output_path, review_rows)
        print(f"Saved {output_path}")

    with open(REVIEW_FILE, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["market_id", "reason", "candidate_question", "candidate_slug"],
        )
        writer.writeheader()
        for row in review_rows:
            writer.writerow(row)

    print(f"Review file saved to {REVIEW_FILE}")
    print(f"Review rows: {len(review_rows)}")


if __name__ == "__main__":
    main()
