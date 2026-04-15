from src.types_live import Signal, Portfolio


def compute_trade_size(
    signal: Signal,
    portfolio: Portfolio,
    max_position_size: float,
    edge_size_multiplier: float
) -> float:

    # No trade
    if signal.action == "HOLD":
        return 0.0

    # Get current position
    positions_in_market = portfolio.positions.get(
        signal.market_id,
        {
            "YES": {"size": 0.0, "avg_price": 0.0},
            "NO": {"size": 0.0, "avg_price": 0.0}
        }
    )

    yes_size = positions_in_market["YES"]["size"]
    no_size = positions_in_market["NO"]["size"]

    # Determine current exposure on the same side
    if signal.action == "BUY_YES":
        current_same_side_size = yes_size
    elif signal.action == "BUY_NO":
        current_same_side_size = no_size
    else:
        return 0.0

    # Remaining capacity
    remaining_room = max_position_size - current_same_side_size
    if remaining_room <= 0:
        return 0.0

    # -----------------------------
    # NEW SIZING LOGIC
    # -----------------------------

    abs_edge = abs(signal.edge)
    p = signal.market_prob

    # Variance weighting (max at p=0.5, zero at extremes)
    variance_factor = p * (1.0 - p)

    # Scale factor so sizes are not too small
    # (since p*(1-p) max is 0.25)
    normalized_variance = variance_factor * 4.0

    # Final size
    raw_size = abs_edge * edge_size_multiplier * normalized_variance

    if raw_size <= 0:
        return 0.0

    return min(raw_size, remaining_room)