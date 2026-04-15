from src.types_live import MarketState, Signal
from src.features_live import compute_midpoint
from src.config_live import (
    INVERT_SIGNAL,
    MIN_MARKET_PROB,
    MAX_MARKET_PROB,
)


def generate_signal(market: MarketState, model_prob: float, threshold: float) -> Signal:
    market_prob = compute_midpoint(market.best_bid, market.best_ask)
    edge = model_prob - market_prob

    # Probability filter:
    # skip extreme markets where payoff skew / tail risk gets worse
    if not (MIN_MARKET_PROB < market_prob < MAX_MARKET_PROB):
        action = "HOLD"
    else:
        if INVERT_SIGNAL:
            # Inverted logic discovered empirically
            if edge > threshold:
                action = "BUY_NO"
            elif edge < -threshold:
                action = "BUY_YES"
            else:
                action = "HOLD"
        else:
            # Original direction
            if edge > threshold:
                action = "BUY_YES"
            elif edge < -threshold:
                action = "BUY_NO"
            else:
                action = "HOLD"

    return Signal(
        market_id=market.market_id,
        model_prob=model_prob,
        market_prob=market_prob,
        edge=edge,
        action=action
    )
