import csv
import os
from datetime import datetime, timedelta


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "historical", "historical_data.csv")

# Keep this small and truthful.
# Binary market convention:
# YES = home team wins
# NO  = home team does not win
#
# For each match:
# - pregame row: Polymarket probability as market price, bookmaker fair home-win probability as model_prob
# - settlement row: 1.0 if home won, else 0.0

TOTAL_SYNTHETIC_SPREAD = 0.02


MANUAL_MATCHES = [
    {
        "match_date": "2025-05-19",
        "home_team": "Brighton",
        "away_team": "Liverpool",

        # Real bookmaker closing odds (fill these from Football-Data)
        # Example columns to use:
        # AvgCH, AvgCD, AvgCA  or  B365CH, B365CD, B365CA
        "bookmaker_home_odds": None,
        "bookmaker_draw_odds": None,
        "bookmaker_away_odds": None,

        # Real Polymarket implied probability for YES = home team wins
        # Fill from Polymarket market page / API near pregame
        "polymarket_yes_prob": None,

        # Actual result:
        # H = home win, D = draw, A = away win
        "result": None,
    },
    {
        "match_date": "2025-05-25",
        "home_team": "Liverpool",
        "away_team": "Crystal Palace",
        "bookmaker_home_odds": None,
        "bookmaker_draw_odds": None,
        "bookmaker_away_odds": None,
        "polymarket_yes_prob": None,
        "result": None,
    },
]


def ensure_dirs() -> None:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)


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
        best_bid = prob
        best_ask = prob

    return best_bid, best_ask


def build_market_id(match_date: str, home_team: str, away_team: str) -> str:
    dt = datetime.strptime(match_date, "%Y-%m-%d")
    home_slug = home_team.lower().replace(" ", "_")
    away_slug = away_team.lower().replace(" ", "_")
    return f"manual_{dt.strftime('%Y%m%d')}_{home_slug}_vs_{away_slug}_home_win"


def settle_prob_from_result(result: str) -> float:
    if result == "H":
        return 1.0
    if result in {"D", "A"}:
        return 0.0
    raise ValueError(f"Unexpected result value: {result}")


def validate_match_row(row: dict) -> None:
    required_numeric = [
        "bookmaker_home_odds",
        "bookmaker_draw_odds",
        "bookmaker_away_odds",
        "polymarket_yes_prob",
    ]

    for key in required_numeric:
        value = row.get(key)
        if value is None:
            raise ValueError(f"Missing value for {key} in match {row.get('home_team')} vs {row.get('away_team')}")

    if row["result"] not in {"H", "D", "A"}:
        raise ValueError(f"Invalid result in match {row.get('home_team')} vs {row.get('away_team')}: {row['result']}")

    p = float(row["polymarket_yes_prob"])
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"Polymarket prob out of bounds: {p}")


def build_rows():
    output_rows = []

    for match in MANUAL_MATCHES:
        validate_match_row(match)

        market_id = build_market_id(
            match["match_date"],
            match["home_team"],
            match["away_team"]
        )

        bookmaker_home_prob, _, _ = fair_probs_from_decimal_odds(
            float(match["bookmaker_home_odds"]),
            float(match["bookmaker_draw_odds"]),
            float(match["bookmaker_away_odds"]),
        )

        market_prob = float(match["polymarket_yes_prob"])
        best_bid, best_ask = clipped_bid_ask(market_prob, TOTAL_SYNTHETIC_SPREAD)

        match_dt = datetime.strptime(match["match_date"], "%Y-%m-%d")
        pregame_ts = match_dt.replace(hour=12, minute=0, second=0).isoformat()
        settle_ts = (match_dt + timedelta(days=1)).replace(hour=12, minute=0, second=0).isoformat()

        output_rows.append({
            "timestamp": pregame_ts,
            "market_id": market_id,
            "best_bid": f"{best_bid:.6f}",
            "best_ask": f"{best_ask:.6f}",
            "bookmaker_prob": f"{bookmaker_home_prob:.6f}",
        })

        settled_prob = settle_prob_from_result(match["result"])

        output_rows.append({
            "timestamp": settle_ts,
            "market_id": market_id,
            "best_bid": f"{settled_prob:.6f}",
            "best_ask": f"{settled_prob:.6f}",
            "bookmaker_prob": f"{settled_prob:.6f}",
        })

    output_rows.sort(key=lambda x: (x["timestamp"], x["market_id"]))
    return output_rows


def write_historical_csv(rows):
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["timestamp", "market_id", "best_bid", "best_ask", "bookmaker_prob"]
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    ensure_dirs()
    rows = build_rows()
    write_historical_csv(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
