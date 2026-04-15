from src.types_live import Portfolio


def validate_portfolio_state(portfolio: Portfolio) -> None:
    if portfolio.cash < -1e-9:
        raise ValueError(f"Portfolio cash went negative: {portfolio.cash:.6f}")

    for market_id, positions in portfolio.positions.items():
        yes_size = positions["YES"]["size"]
        yes_avg = positions["YES"]["avg_price"]
        no_size = positions["NO"]["size"]
        no_avg = positions["NO"]["avg_price"]

        if yes_size < -1e-9:
            raise ValueError(f"{market_id}: YES size negative: {yes_size:.6f}")

        if no_size < -1e-9:
            raise ValueError(f"{market_id}: NO size negative: {no_size:.6f}")

        if yes_size > 0 and no_size > 0:
            raise ValueError(
                f"{market_id}: simultaneous YES and NO positions detected "
                f"(YES={yes_size:.6f}, NO={no_size:.6f})"
            )

        if yes_size == 0 and abs(yes_avg) > 1e-9:
            raise ValueError(f"{market_id}: YES avg_price nonzero with zero size: {yes_avg:.6f}")

        if no_size == 0 and abs(no_avg) > 1e-9:
            raise ValueError(f"{market_id}: NO avg_price nonzero with zero size: {no_avg:.6f}")

        if yes_size > 0 and not (0.0 <= yes_avg <= 1.0):
            raise ValueError(f"{market_id}: YES avg_price out of bounds: {yes_avg:.6f}")

        if no_size > 0 and not (0.0 <= no_avg <= 1.0):
            raise ValueError(f"{market_id}: NO avg_price out of bounds: {no_avg:.6f}")