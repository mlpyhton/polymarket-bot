def compute_midpoint(best_bid: float, best_ask: float) -> float:
    return (best_bid + best_ask) / 2


def compute_spread(best_bid: float, best_ask: float) -> float:
    return best_ask - best_bid