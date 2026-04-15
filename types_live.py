from dataclasses import dataclass


@dataclass
class MarketState:
    market_id: str
    best_bid: float
    best_ask: float


@dataclass
class Signal:
    market_id: str
    model_prob: float
    market_prob: float
    edge: float
    action: str


@dataclass
class Fill:
    market_id: str
    side: str
    price: float
    size: float


@dataclass
class Portfolio:
    cash: float
    positions: dict