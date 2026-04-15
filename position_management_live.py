from src.features_live import compute_midpoint
from src.portfolio_live import close_position


def check_exit_conditions(portfolio, market, take_profit: float, stop_loss: float):
    """
    Event-native version:
    Exit only when the market resolves to 0 or 1.
    """

    midpoint = compute_midpoint(market.best_bid, market.best_ask)
    
    if midpoint <= 0.01 or midpoint >= 0.99:
        positions_in_market = portfolio.positions.get(
            market.market_id,
            {
                "YES": {"size": 0.0, "avg_price": 0.0},
                "NO": {"size": 0.0, "avg_price": 0.0}
            }
        )

        yes_size = positions_in_market["YES"]["size"]
        no_size = positions_in_market["NO"]["size"]

        if yes_size > 0:
            realized_pnl = close_position(portfolio, market, "YES")
            return True, "market resolved YES", "YES", realized_pnl

        if no_size > 0:
            realized_pnl = close_position(portfolio, market, "NO")
            return True, "market resolved NO", "NO", realized_pnl

    return False, "no exit", "", 0.0