from src.types_live import Signal, Portfolio


def get_trade_decision(signal: Signal, portfolio: Portfolio, max_position_size: float):
    """
    Event-native logic:
    - Only ONE trade per market
    - No flipping
    - No adding after entry
    """

    if signal.action == "HOLD":
        return False, "HOLD signal"

    market_positions = portfolio.positions.get(signal.market_id)

    # 🚫 already in market → do nothing
    if market_positions:
        yes_size = market_positions["YES"]["size"]
        no_size = market_positions["NO"]["size"]

        if yes_size > 0 or no_size > 0:
            return False, "already in market"

    return True, "approved"