import os
import csv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_DIR = os.path.join(BASE_DIR, "src", "data", "historical_ready")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "historical", "historical_data.csv")

REQUIRED_COLUMNS = [
    "timestamp",
    "market_id",
    "best_bid",
    "best_ask",
    "bookmaker_prob",
]


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


def is_valid_pregame_row(row: dict) -> bool:
    try:
        bid = float(row["best_bid"])
        ask = float(row["best_ask"])
        prob = float(row["bookmaker_prob"])

        if not (0.0 < prob < 1.0):
            return False

        if not (0.0 < bid < 1.0):
            return False

        if not (0.0 < ask < 1.0):
            return False

        if bid > ask:
            return False

        return True

    except Exception:
        return False


def is_valid_row(row: dict) -> bool:
    return is_settlement_row(row) or is_valid_pregame_row(row)


def load_file(filepath: str):
    rows = []

    with open(filepath, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for col in REQUIRED_COLUMNS:
            if col not in reader.fieldnames:
                raise ValueError(f"{filepath} missing column: {col}")

        for row in reader:
            if is_valid_row(row):
                rows.append(row)

    return rows


def merge_all_files():
    all_rows = []

    files = [
        f for f in os.listdir(RAW_DIR)
        if f.endswith(".csv")
    ]

    if not files:
        raise ValueError(f"No CSV files found in {RAW_DIR}")

    print(f"Found {len(files)} files")

    for file in files:
        path = os.path.join(RAW_DIR, file)
        rows = load_file(path)

        print(f"{file}: {len(rows)} valid rows")
        all_rows.extend(rows)

    all_rows.sort(key=lambda x: (x["timestamp"], x["market_id"]))

    print(f"\nTOTAL ROWS: {len(all_rows)}")
    return all_rows


def save_output(rows):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved merged file → {OUTPUT_FILE}")


def main():
    rows = merge_all_files()
    save_output(rows)


if __name__ == "__main__":
    main()
