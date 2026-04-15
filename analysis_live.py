import csv
import os
import numpy as np
import matplotlib.pyplot as plt


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


EDGE_BUCKETS = [
    (0.007, 0.010),
    (0.010, 0.015),
    (0.015, 0.020),
    (0.020, float("inf")),
]


def get_latest_run_filepath(base_dir: str) -> str:
    logs_dir = os.path.join(base_dir, "data", "logs")
    existing_files = os.listdir(logs_dir)

    run_numbers = []

    for filename in existing_files:
        if filename.startswith("run_") and filename.endswith(".csv"):
            try:
                number = int(filename.split("_")[1].split(".")[0])
                run_numbers.append(number)
            except ValueError:
                pass

    if not run_numbers:
        raise FileNotFoundError("No run_*.csv files found in data/logs")

    latest_run_number = max(run_numbers)
    return os.path.join(logs_dir, f"run_{latest_run_number}.csv")


def load_run_data(filepath: str):
    timestamps = []
    equity = []
    drawdowns = []
    trade_count = 0
    realized_pnls = []

    with open(filepath, mode="r", newline="") as file:
        reader = csv.DictReader(file)

        peak = None

        for row in reader:
            total_value = row.get("total_value")
            if total_value in (None, "", "None"):
                continue

            timestamp = row["timestamp"]
            value = float(total_value)

            timestamps.append(timestamp)
            equity.append(value)

            if row.get("fill_side", "") != "":
                trade_count += 1

            realized = row.get("realized_pnl")
            if realized not in (None, "", "None"):
                realized_value = float(realized)
                if abs(realized_value) > 1e-12:
                    realized_pnls.append(realized_value)

            if peak is None or value > peak:
                peak = value

            drawdowns.append(peak - value)

    return timestamps, equity, drawdowns, trade_count, realized_pnls


def compute_metrics(equity):
    returns = np.diff(equity)

    if len(returns) == 0:
        return {
            "avg_return": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
        }

    avg_return = np.mean(returns)
    std_return = np.std(returns)

    sharpe = 0.0
    if std_return > 0:
        sharpe = avg_return / std_return

    downside = returns[returns < 0]
    sortino = 0.0
    if len(downside) > 0 and np.std(downside) > 0:
        sortino = avg_return / np.std(downside)

    return {
        "avg_return": avg_return,
        "sharpe": sharpe,
        "sortino": sortino,
    }


def summarize_run(filepath: str):
    timestamps, equity, drawdowns, trade_count, realized_pnls = load_run_data(filepath)

    if not equity:
        print("No data found.")
        return

    resolve_yes = 0
    resolve_no = 0
    total_realized_pnl = 0.0

    with open(filepath, mode="r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row.get("exit_triggered") == "True":
                reason = row.get("exit_reason", "").lower()
                if "resolved yes" in reason:
                    resolve_yes += 1
                if "resolved no" in reason:
                    resolve_no += 1

            realized = row.get("realized_pnl")
            if realized not in (None, "", "None"):
                total_realized_pnl += float(realized)

    final_value = equity[-1]
    max_drawdown = max(drawdowns) if drawdowns else 0.0
    total_return = final_value - equity[0]
    avg_return_per_step = total_return / len(equity)
    metrics = compute_metrics(equity)

    wins = [x for x in realized_pnls if x > 0]
    losses = [x for x in realized_pnls if x < 0]
    win_rate = (len(wins) / len(realized_pnls)) if realized_pnls else 0.0
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0

    print("\n=== RUN SUMMARY ===")
    print("File:", os.path.basename(filepath))
    print("Steps:", len(equity))
    print("Total Trades:", trade_count)
    print("Resolved YES Exits:", resolve_yes)
    print("Resolved NO Exits:", resolve_no)
    print("Closed Trades:", len(realized_pnls))
    print("Win Rate:", round(win_rate * 100, 2), "%")
    print("Avg Win:", round(avg_win, 3))
    print("Avg Loss:", round(avg_loss, 3))
    print("Total Realized PnL:", round(total_realized_pnl, 3))
    print("Start Value:", round(equity[0], 3))
    print("Final Value:", round(final_value, 3))
    print("Total Return:", round(total_return, 3))
    print("Max Drawdown:", round(max_drawdown, 3))
    print("Avg Return per Step:", round(avg_return_per_step, 5))
    print("Sharpe:", round(metrics["sharpe"], 4))
    print("Sortino:", round(metrics["sortino"], 4))


def load_closed_trades_with_edges(filepath: str):
    """
    Pair each realized close with the edge from the entry step for the same market.
    Since the strategy is one-entry-per-market, this mapping is clean.
    """
    entry_edge_by_market = {}
    closed_trades = []

    with open(filepath, mode="r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            market_id = row.get("market_id", "")
            fill_side = row.get("fill_side", "")
            edge_raw = row.get("edge", "")
            realized_raw = row.get("realized_pnl", "")
            exit_triggered = row.get("exit_triggered", "")

            # Record entry edge when a fill occurs
            if fill_side != "" and edge_raw not in ("", "None"):
                try:
                    entry_edge_by_market[market_id] = abs(float(edge_raw))
                except ValueError:
                    pass

            # Record close when realized pnl is nonzero on exit
            if exit_triggered == "True" and realized_raw not in ("", "None"):
                try:
                    realized_pnl = float(realized_raw)
                except ValueError:
                    continue

                if abs(realized_pnl) <= 1e-12:
                    continue

                entry_edge = entry_edge_by_market.get(market_id)
                if entry_edge is None:
                    continue

                closed_trades.append({
                    "market_id": market_id,
                    "entry_edge": entry_edge,
                    "realized_pnl": realized_pnl,
                })

    return closed_trades


def bucket_label(low: float, high: float) -> str:
    if high == float("inf"):
        return f">{low:.3f}"
    return f"{low:.3f}-{high:.3f}"


def analyze_edge_buckets(filepath: str):
    closed_trades = load_closed_trades_with_edges(filepath)

    if not closed_trades:
        print("\n=== EDGE BUCKET ANALYSIS ===")
        print("No closed trades found for edge bucket analysis.")
        return

    bucket_stats = []

    for low, high in EDGE_BUCKETS:
        bucket_trades = [
            t for t in closed_trades
            if (t["entry_edge"] >= low) and (t["entry_edge"] < high if high != float("inf") else True)
        ]

        pnls = [t["realized_pnl"] for t in bucket_trades]
        wins = [x for x in pnls if x > 0]
        losses = [x for x in pnls if x < 0]

        trade_count = len(bucket_trades)
        win_rate = (len(wins) / trade_count) if trade_count > 0 else 0.0
        avg_pnl = np.mean(pnls) if pnls else 0.0
        total_pnl = np.sum(pnls) if pnls else 0.0
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        bucket_stats.append({
            "label": bucket_label(low, high),
            "count": trade_count,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        })

    print("\n=== EDGE BUCKET ANALYSIS ===")
    print(
        f"{'Bucket':<12} {'Count':<8} {'WinRate':<10} "
        f"{'AvgPnL':<10} {'TotalPnL':<10} {'AvgWin':<10} {'AvgLoss':<10}"
    )

    for row in bucket_stats:
        print(
            f"{row['label']:<12} "
            f"{row['count']:<8} "
            f"{row['win_rate']*100:<9.2f}% "
            f"{row['avg_pnl']:<10.3f} "
            f"{row['total_pnl']:<10.3f} "
            f"{row['avg_win']:<10.3f} "
            f"{row['avg_loss']:<10.3f}"
        )


def plot_equity_curve(filepath: str):
    _, equity, _, _, _ = load_run_data(filepath)

    plt.figure()
    plt.plot(equity)
    plt.title("Equity Curve")
    plt.xlabel("Step")
    plt.ylabel("Portfolio Value")
    plt.grid()
    plt.show()


def plot_equity_and_drawdown(filepath: str):
    _, equity, drawdowns, _, _ = load_run_data(filepath)

    plt.figure()
    plt.plot(equity, label="Equity")
    plt.plot(drawdowns, label="Drawdown")
    plt.legend()
    plt.title("Equity & Drawdown")
    plt.xlabel("Step")
    plt.grid()
    plt.show()


def plot_realized_pnl_distribution(filepath: str):
    _, _, _, _, realized_pnls = load_run_data(filepath)

    if not realized_pnls:
        return

    plt.figure()
    plt.hist(realized_pnls, bins=20)
    plt.title("Realized Trade PnL Distribution")
    plt.xlabel("PnL")
    plt.ylabel("Frequency")
    plt.grid()
    plt.show()


def load_run_metadata():
    metadata_path = os.path.join(BASE_DIR, "data", "run_metadata.csv")

    if not os.path.exists(metadata_path):
        return {}

    metadata = {}

    with open(metadata_path, mode="r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            run_file = row["run_file"]
            metadata[run_file] = row

    return metadata


def compute_run_summary(filepath: str):
    _, equity, drawdowns, trade_count, realized_pnls = load_run_data(filepath)

    if not equity:
        return None

    resolve_yes = 0
    resolve_no = 0
    total_realized_pnl = 0.0

    with open(filepath, mode="r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row.get("exit_triggered") == "True":
                reason = row.get("exit_reason", "").lower()
                if "resolved yes" in reason:
                    resolve_yes += 1
                if "resolved no" in reason:
                    resolve_no += 1

            realized = row.get("realized_pnl")
            if realized not in (None, "", "None"):
                total_realized_pnl += float(realized)

    final_value = equity[-1]
    start_value = equity[0]
    total_return = final_value - start_value
    max_drawdown = max(drawdowns) if drawdowns else 0.0
    metrics = compute_metrics(equity)

    wins = [x for x in realized_pnls if x > 0]
    win_rate = (len(wins) / len(realized_pnls)) if realized_pnls else 0.0

    return {
        "start_value": start_value,
        "final_value": final_value,
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "trade_count": trade_count,
        "resolve_yes": resolve_yes,
        "resolve_no": resolve_no,
        "realized_pnl": total_realized_pnl,
        "closed_trades": len(realized_pnls),
        "win_rate": win_rate,
        "sharpe": metrics["sharpe"],
        "sortino": metrics["sortino"],
    }


def build_leaderboard():
    logs_dir = os.path.join(BASE_DIR, "data", "logs")
    metadata = load_run_metadata()

    rows = []

    for file in os.listdir(logs_dir):
        if not (file.startswith("run_") and file.endswith(".csv")):
            continue

        filepath = os.path.join(logs_dir, file)
        summary = compute_run_summary(filepath)

        if summary is None:
            continue

        meta = metadata.get(file, {})

        row = {
            "run_file": file,
            "threshold": meta.get("threshold", ""),
            "take_profit": meta.get("take_profit", ""),
            "stop_loss": meta.get("stop_loss", ""),
            "trade_size": meta.get("trade_size", ""),
            "edge_size_multiplier": meta.get("edge_size_multiplier", ""),
            "final_value": round(summary["final_value"], 3),
            "total_return": round(summary["total_return"], 3),
            "max_drawdown": round(summary["max_drawdown"], 3),
            "trade_count": summary["trade_count"],
            "closed_trades": summary["closed_trades"],
            "win_rate": round(summary["win_rate"], 3),
            "resolve_yes": summary["resolve_yes"],
            "resolve_no": summary["resolve_no"],
            "realized_pnl": round(summary["realized_pnl"], 3),
            "sharpe": round(summary["sharpe"], 4),
            "sortino": round(summary["sortino"], 4),
            "score": round(summary["final_value"] - 0.5 * summary["max_drawdown"], 3),
        }

        rows.append(row)

    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


def save_leaderboard(rows):
    output_path = os.path.join(BASE_DIR, "data", "leaderboard.csv")

    with open(output_path, mode="w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "run_file",
                "threshold",
                "take_profit",
                "stop_loss",
                "trade_size",
                "edge_size_multiplier",
                "final_value",
                "total_return",
                "max_drawdown",
                "trade_count",
                "closed_trades",
                "win_rate",
                "resolve_yes",
                "resolve_no",
                "realized_pnl",
                "sharpe",
                "sortino",
                "score",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def print_leaderboard(rows, top_n=10):
    print("\n=== LEADERBOARD ===")
    print(
        f"{'Run':<10} {'Thr':<8} {'ESM':<8} {'Final':<10} "
        f"{'Return':<10} {'DD':<8} {'Trades':<8} {'Closed':<8} {'WinRt':<8} {'Score':<10}"
    )

    for row in rows[:top_n]:
        print(
            f"{row['run_file']:<10} "
            f"{str(row['threshold']):<8} "
            f"{str(row['edge_size_multiplier']):<8} "
            f"{row['final_value']:<10} "
            f"{row['total_return']:<10} "
            f"{row['max_drawdown']:<8} "
            f"{row['trade_count']:<8} "
            f"{row['closed_trades']:<8} "
            f"{row['win_rate']:<8} "
            f"{row['score']:<10}"
        )


if __name__ == "__main__":
    filepath = get_latest_run_filepath(BASE_DIR)
    print("Analyzing:", filepath)

    summarize_run(filepath)
    analyze_edge_buckets(filepath)
    plot_equity_curve(filepath)
    plot_equity_and_drawdown(filepath)
    plot_realized_pnl_distribution(filepath)

    leaderboard = build_leaderboard()
    save_leaderboard(leaderboard)
    print_leaderboard(leaderboard)