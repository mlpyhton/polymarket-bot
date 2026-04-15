import csv
import os

from src.features_live import compute_midpoint, compute_spread
from src.portfolio_live import (
    compute_portfolio_value,
    compute_unrealized_pnl,
    compute_side_unrealized_pnl,
)
from src.config_live import STARTING_CASH


def initialize_csv_log(filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    file_exists = os.path.exists(filepath)

    if not file_exists:
        with open(filepath, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                "timestamp",
                "step",
                "market_id",
                "action",
                "approved",
                "reason",
                "model_prob",
                "market_prob",
                "edge",
                "best_bid",
                "best_ask",
                "midpoint",
                "spread",
                "fill_side",
                "fill_price",
                "fill_size",
                "cash",
                "yes_size",
                "yes_avg_price",
                "no_size",
                "no_avg_price",
                "yes_pnl",
                "no_pnl",
                "unrealized_pnl",
                "exit_triggered",
                "exit_reason",
                "exit_side",
                "realized_pnl",
                "total_value"
            ])


def log_step_to_csv(
    filepath: str,
    step: int,
    timestamp: str,
    signal,
    approved: bool,
    reason: str,
    fill,
    portfolio,
    market,
    exit_triggered: bool,
    exit_reason: str,
    exit_side: str,
    realized_pnl: float
) -> None:
    midpoint = compute_midpoint(market.best_bid, market.best_ask)
    spread = compute_spread(market.best_bid, market.best_ask)
    total_value = compute_portfolio_value(portfolio, market)
    unrealized_pnl = compute_unrealized_pnl(portfolio, market, STARTING_CASH)
    side_pnl = compute_side_unrealized_pnl(portfolio, market)

    positions_in_market = portfolio.positions.get(
        market.market_id,
        {
            "YES": {"size": 0.0, "avg_price": 0.0},
            "NO": {"size": 0.0, "avg_price": 0.0}
        }
    )

    yes_size = positions_in_market["YES"]["size"]
    yes_avg_price = positions_in_market["YES"]["avg_price"]
    no_size = positions_in_market["NO"]["size"]
    no_avg_price = positions_in_market["NO"]["avg_price"]

    fill_side = ""
    fill_price = ""
    fill_size = ""

    if fill is not None:
        fill_side = fill.side
        fill_price = fill.price
        fill_size = fill.size

    market_id = market.market_id
    action = "NO_NEW_SIGNAL"
    model_prob = 0.0
    market_prob = midpoint
    edge = 0.0

    if signal is not None:
        market_id = signal.market_id
        action = signal.action
        model_prob = signal.model_prob
        market_prob = signal.market_prob
        edge = signal.edge

    with open(filepath, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            timestamp,
            step,
            market_id,
            action,
            approved,
            reason,
            model_prob,
            market_prob,
            edge,
            market.best_bid,
            market.best_ask,
            midpoint,
            spread,
            fill_side,
            fill_price,
            fill_size,
            portfolio.cash,
            yes_size,
            yes_avg_price,
            no_size,
            no_avg_price,
            side_pnl["YES"],
            side_pnl["NO"],
            unrealized_pnl,
            exit_triggered,
            exit_reason,
            exit_side,
            realized_pnl,
            total_value
        ])
