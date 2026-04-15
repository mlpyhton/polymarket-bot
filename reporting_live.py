from src.types_live import Portfolio, MarketState
from src.features_live import compute_midpoint, compute_spread
from src.portfolio_live import (
    compute_portfolio_value,
    compute_unrealized_pnl,
    compute_side_unrealized_pnl,
)
from src.config_live import STARTING_CASH


def print_header(title: str) -> None:
    print("\n" + "=" * 48)
    print(title)
    print("=" * 48)


def report_state(
    signal,
    approved: bool,
    reason: str,
    fill,
    portfolio: Portfolio,
    market: MarketState,
    exit_triggered: bool = False,
    exit_reason: str = "",
    exit_side: str = "",
    realized_pnl: float = 0.0,
    step_pnl: float = 0.0
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
    yes_avg = positions_in_market["YES"]["avg_price"]
    no_size = positions_in_market["NO"]["size"]
    no_avg = positions_in_market["NO"]["avg_price"]
    total_exposure = yes_size + no_size

    if signal is None:
        market_id = market.market_id
        action = "NO_NEW_SIGNAL"
        model_prob = 0.0
        market_prob = midpoint
        edge = 0.0
        edge_strength = 0.0
    else:
        market_id = signal.market_id
        action = signal.action
        model_prob = signal.model_prob
        market_prob = signal.market_prob
        edge = signal.edge
        edge_strength = abs(edge)

    print("\n" + "=" * 48)
    print("BOT STATE")
    print("=" * 48)

    print("[Market]")
    print(f"Market         : {market_id}")
    print(f"Best Bid       : {market.best_bid:.3f}")
    print(f"Best Ask       : {market.best_ask:.3f}")
    print(f"Midpoint       : {midpoint:.3f}")
    print(f"Spread         : {spread:.3f}")

    print("\n[Signal]")
    print(f"Action         : {action}")
    print(f"Approved       : {approved}")
    print(f"Reason         : {reason}")
    print(f"Model Prob     : {model_prob:.3f}")
    print(f"Market Prob    : {market_prob:.3f}")
    print(f"Edge           : {edge:.3f}")
    print(f"Edge Strength  : {edge_strength:.3f}")

    print("\n[Execution]")
    if fill is None:
        print("Fill           : None")
    else:
        print(f"Fill Side      : {fill.side}")
        print(f"Fill Price     : {fill.price:.3f}")
        print(f"Fill Size      : {fill.size:.3f}")

    print("\n[Portfolio]")
    print(f"Cash           : {portfolio.cash:.3f}")
    print(f"YES Position   : size={yes_size:.3f} | avg={yes_avg:.3f}")
    print(f"NO Position    : size={no_size:.3f} | avg={no_avg:.3f}")
    print(f"Exposure       : {total_exposure:.3f}")

    print("\n[PnL]")
    print(f"YES PnL        : {side_pnl['YES']:.3f}")
    print(f"NO PnL         : {side_pnl['NO']:.3f}")
    print(f"Unrealized PnL : {unrealized_pnl:.3f}")
    print(f"Realized PnL   : {realized_pnl:.3f}")
    print(f"Step PnL       : {step_pnl:.3f}")
    print(f"Total Value    : {total_value:.3f}")

    print("\n[Exit]")
    print(f"Exit Triggered : {exit_triggered}")
    print(f"Exit Reason    : {exit_reason}")
    print(f"Exit Side      : {exit_side}")

    print("=" * 48)


def report_summary(
    total_trades: int,
    buy_yes_count: int,
    buy_no_count: int,
    hold_count: int,
    risk_rejection_count: int,
    peak_value: float,
    max_drawdown: float,
    final_value: float
) -> None:
    total_return = final_value - STARTING_CASH
    total_return_pct = (total_return / STARTING_CASH) * 100 if STARTING_CASH > 0 else 0.0

    print_header("SIMULATION SUMMARY")
    print(f"Start Value    : {STARTING_CASH:.3f}")
    print(f"Final Value    : {final_value:.3f}")
    print(f"Total Return   : {total_return:.3f}")
    print(f"Return %       : {total_return_pct:.2f}%")
    print(f"Total Trades   : {total_trades}")
    print(f"BUY_YES        : {buy_yes_count}")
    print(f"BUY_NO         : {buy_no_count}")
    print(f"HOLD Signals   : {hold_count}")
    print(f"Risk Rejected  : {risk_rejection_count}")
    print(f"Peak Value     : {peak_value:.3f}")
    print(f"Max Drawdown   : {max_drawdown:.3f}")