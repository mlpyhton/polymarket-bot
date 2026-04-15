from src.types_live import Signal, MarketState, Fill


# 🔧 CONFIG (keep simple for now)
BASE_SLIPPAGE = 0.002      # 0.2% baseline slippage
SIZE_IMPACT = 0.0005       # extra slippage per unit size


def compute_slippage(size: float) -> float:
    return BASE_SLIPPAGE + SIZE_IMPACT * size


def simulate_fill(signal: Signal, market: MarketState, size: float):
    if signal.action == "HOLD":
        return None

    slippage = compute_slippage(size)

    if signal.action == "BUY_YES":
        raw_price = market.best_ask
        price = min(1.0, raw_price + slippage)

        return Fill(
            market_id=market.market_id,
            side="BUY_YES",
            price=price,
            size=size
        )

    if signal.action == "BUY_NO":
        raw_price = 1.0 - market.best_bid
        price = min(1.0, raw_price + slippage)

        return Fill(
            market_id=market.market_id,
            side="BUY_NO",
            price=price,
            size=size
        )

    return None