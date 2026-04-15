from src.types_live import Portfolio, Fill, MarketState
from src.features_live import compute_midpoint


def create_portfolio(starting_cash: float) -> Portfolio:
    return Portfolio(
        cash=starting_cash,
        positions={}
    )


# 🔥 UPDATED: returns REALIZED PnL
def close_position(portfolio: Portfolio, market: MarketState, side: str) -> float:
    if market.market_id not in portfolio.positions:
        return 0.0

    positions_in_market = portfolio.positions[market.market_id]

    if side == "YES":
        side_data = positions_in_market["YES"]
        close_price = compute_midpoint(market.best_bid, market.best_ask)
    elif side == "NO":
        side_data = positions_in_market["NO"]
        close_price = 1 - compute_midpoint(market.best_bid, market.best_ask)
    else:
        return 0.0

    size = side_data["size"]
    avg_price = side_data["avg_price"]

    if size <= 0:
        return 0.0

    # 💡 KEY CHANGE
    realized_pnl = size * (close_price - avg_price)

    cash_return = size * close_price
    portfolio.cash += cash_return

    side_data["size"] = 0.0
    side_data["avg_price"] = 0.0

    return realized_pnl


def apply_fill(portfolio: Portfolio, fill: Fill, market: MarketState) -> None:
    if fill.market_id not in portfolio.positions:
        portfolio.positions[fill.market_id] = {
            "YES": {"size": 0.0, "avg_price": 0.0},
            "NO": {"size": 0.0, "avg_price": 0.0}
        }

    market_positions = portfolio.positions[fill.market_id]

    if fill.side == "BUY_YES":
        if market_positions["NO"]["size"] > 0:
            close_position(portfolio, market, "NO")

        portfolio.cash -= fill.price * fill.size
        side_data = market_positions["YES"]

    elif fill.side == "BUY_NO":
        if market_positions["YES"]["size"] > 0:
            close_position(portfolio, market, "YES")

        portfolio.cash -= fill.price * fill.size
        side_data = market_positions["NO"]

    else:
        return

    old_size = side_data["size"]
    old_avg = side_data["avg_price"]

    new_size = old_size + fill.size

    if new_size > 0:
        new_avg = ((old_size * old_avg) + (fill.size * fill.price)) / new_size
    else:
        new_avg = 0.0

    side_data["size"] = new_size
    side_data["avg_price"] = new_avg


def compute_portfolio_value(portfolio: Portfolio, market: MarketState) -> float:
    midpoint = compute_midpoint(market.best_bid, market.best_ask)

    positions_in_market = portfolio.positions.get(
        market.market_id,
        {
            "YES": {"size": 0.0, "avg_price": 0.0},
            "NO": {"size": 0.0, "avg_price": 0.0}
        }
    )

    yes_size = positions_in_market["YES"]["size"]
    no_size = positions_in_market["NO"]["size"]

    yes_value = yes_size * midpoint
    no_value = no_size * (1 - midpoint)

    return portfolio.cash + yes_value + no_value


def compute_unrealized_pnl(portfolio: Portfolio, market: MarketState, starting_cash: float) -> float:
    total_value = compute_portfolio_value(portfolio, market)
    return total_value - starting_cash


def compute_side_unrealized_pnl(portfolio: Portfolio, market: MarketState) -> dict:
    midpoint = compute_midpoint(market.best_bid, market.best_ask)

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

    yes_market_price = midpoint
    no_market_price = 1 - midpoint

    yes_pnl = yes_size * (yes_market_price - yes_avg)
    no_pnl = no_size * (no_market_price - no_avg)

    return {
        "YES": yes_pnl,
        "NO": no_pnl,
        "TOTAL": yes_pnl + no_pnl
    }
