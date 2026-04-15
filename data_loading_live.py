import csv
from datetime import datetime

from src.types_live import MarketState
from src.config_live import TEST_MARKET_ID


def load_test_markets() -> list:
    return [
        MarketState(TEST_MARKET_ID, 0.52, 0.55),
        MarketState(TEST_MARKET_ID, 0.50, 0.54),
        MarketState(TEST_MARKET_ID, 0.53, 0.54),
        MarketState(TEST_MARKET_ID, 0.57, 0.60),
        MarketState(TEST_MARKET_ID, 0.51, 0.53),
    ]


def parse_timestamp(timestamp_str: str) -> datetime:
    return datetime.fromisoformat(timestamp_str)


def load_historical_data(filepath: str):
    historical_data = []

    with open(filepath, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            timestamp = row["timestamp"].strip()

            market = MarketState(
                market_id=row["market_id"].strip(),
                best_bid=float(row["best_bid"]),
                best_ask=float(row["best_ask"]),
            )

            # This is your model side:
            # bookmaker fair / normalized probability
            model_prob = float(row["bookmaker_prob"])

            historical_data.append((timestamp, market, model_prob))

    historical_data.sort(key=lambda x: parse_timestamp(x[0]))
    return historical_data