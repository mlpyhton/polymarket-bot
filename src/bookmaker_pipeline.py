import csv
import os
from datetime import datetime, timedelta
from urllib.request import urlopen


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SEASON_CODE = "2425"   # 2024/25
DIVISION_CODE = "E0"   # Premier League

RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
HISTORICAL_DIR = os.path.join(BASE_DIR, "data", "historical")

RAW_CSV_PATH = os.path.join(RAW_DIR, f"{DIVISION_CODE}_{SEASON_CODE}.csv")
OUTPUT_CSV_PATH = os.path.join(HISTORICAL_DIR, "historical_data.csv")

CSV_URL = f"https://www.football-data.co.uk/mmz4281/{SEASON_CODE}/{DIVISION_CODE}.csv"

# We synthesize a small bid/ask around the market probability because bookmaker
# closing odds are snapshot probabilities, not an order book.
TOTAL_SYNTHETIC_SPREAD = 0.02

# Preferred columns:
# market = average closing odds
# model  = bet365 closing odds
MARKET_COLUMN_SETS = [
    ("AvgCH", "AvgCD", "AvgCA"),   # average closing odds
    ("AvgH", "AvgD", "AvgA"),      # fallback older-style average odds
]

MODEL_COLUMN_SETS = [
    ("B365CH", "B365CD", "B365CA"),  # bet365 closing odds
    ("B365H", "B365D", "B365A"),     # fallback pre-closing
    ("PSCH", "PSCD", "PSCA"),        # Pinnacle-ish closing fallback
    ("PSH", "PSD", "PSA"),           # fallback pre-closing
]


def ensure_dirs() -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(HISTORICAL_DIR, exist_ok=True)


def download_csv(url: str, filepath: str) -> None:
    with urlopen(url) as response:
        content = response.read().decode("utf-8", errors="replace")

    with open(filepath, "w", encoding="utf-8", newline="") as file:
        file.write(content)


def parse_date(date_str: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unsupported date format: {date_str}")


def safe_float(value: str):
    if value is None:
        return None

    value = str(value).strip()
    if value == "":
        return None

    try:
        x = float(value)
        if x <= 0:
            return None
        return x
    except ValueError:
        return None


def select_odds_triplet(row: dict, column_sets: list[tuple[str, str, str]]):
    for cols in column_sets:
        values = [safe_float(row.get(col)) for col in cols]
        if all(v is not None for v in values):
            return values
    return None


def fair_probs_from_decimal_odds(home_odds: float, draw_odds: float, away_odds: float):
    raw_home = 1.0 / home_odds
    raw_draw = 1.0 / draw_odds
    raw_away = 1.0 / away_odds

    total = raw_home + raw_draw + raw_away

    return (
        raw_home / total,
        raw_draw / total,
        raw_away / total,
    )


def clipped_bid_ask(prob: float, total_spread: float):
    half = total_spread / 2.0
    best_bid = max(0.0, prob - half)
    best_ask = min(1.0, prob + half)

    if best_bid > best_ask:
        best_bid = best_ask = prob

    return best_bid, best_ask


def build_market_id(match_date: datetime, home_team: str, away_team: str) -> str:
    home_slug = home_team.lower().replace(" ", "_")
    away_slug = away_team.lower().replace(" ", "_")
    return f"epl_{match_date.strftime('%Y%m%d')}_{home_slug}_vs_{away_slug}_home_win"


def result_to_home_yes_prob(ftr: str) -> float:
    # Binary market = "home team wins"
    return 1.0 if ftr == "H" else 0.0


def convert_raw_to_historical(raw_csv_path: str, output_csv_path: str) -> int:
    rows_out = []

    with open(raw_csv_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            date_str = row.get("Date", "").strip()
            home_team = row.get("HomeTeam", "").strip()
            away_team = row.get("AwayTeam", "").strip()
            ftr = row.get("FTR", "").strip()

            if not date_str or not home_team or not away_team or ftr not in {"H", "D", "A"}:
                continue

            market_triplet = select_odds_triplet(row, MARKET_COLUMN_SETS)
            model_triplet = select_odds_triplet(row, MODEL_COLUMN_SETS)

            if market_triplet is None or model_triplet is None:
                continue

            market_home, market_draw, market_away = fair_probs_from_decimal_odds(*market_triplet)
            model_home, model_draw, model_away = fair_probs_from_decimal_odds(*model_triplet)

            match_date = parse_date(date_str)
            market_id = build_market_id(match_date, home_team, away_team)

            pre_bid, pre_ask = clipped_bid_ask(market_home, TOTAL_SYNTHETIC_SPREAD)

            # Pre-match row: real closing bookmaker information
            pre_timestamp = (match_date.replace(hour=12, minute=0, second=0)).isoformat()

            rows_out.append({
                "timestamp": pre_timestamp,
                "market_id": market_id,
                "best_bid": f"{pre_bid:.6f}",
                "best_ask": f"{pre_ask:.6f}",
                "bookmaker_prob": f"{model_home:.6f}",
            })

            # Settlement row: actual realized outcome
            settled_prob = result_to_home_yes_prob(ftr)
            settle_timestamp = (match_date + timedelta(days=1)).replace(
                hour=12, minute=0, second=0
            ).isoformat()

            rows_out.append({
                "timestamp": settle_timestamp,
                "market_id": market_id,
                "best_bid": f"{settled_prob:.6f}",
                "best_ask": f"{settled_prob:.6f}",
                "bookmaker_prob": f"{settled_prob:.6f}",
            })

    rows_out.sort(key=lambda x: (x["timestamp"], x["market_id"]))

    with open(output_csv_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["timestamp", "market_id", "best_bid", "best_ask", "bookmaker_prob"]
        )
        writer.writeheader()
        writer.writerows(rows_out)

    return len(rows_out)


def main():
    ensure_dirs()

    print("Downloading raw EPL CSV...")
    download_csv(CSV_URL, RAW_CSV_PATH)
    print(f"Saved raw file to: {RAW_CSV_PATH}")

    print("Converting to bot historical_data.csv...")
    n_rows = convert_raw_to_historical(RAW_CSV_PATH, OUTPUT_CSV_PATH)
    print(f"Saved {n_rows} rows to: {OUTPUT_CSV_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
