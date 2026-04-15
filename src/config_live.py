STARTING_CASH = 1000.0

# Minimum edge needed to trade.
# You can still override this from main_live.py when testing.
THRESHOLD = 0.007

TRADE_SIZE = 15
MAX_POSITION_SIZE = 30

# Event-native setup: TP/SL are no longer the real driver,
# but we keep them for interface compatibility.
TAKE_PROFIT = 0.03
STOP_LOSS = -0.03

TEST_MARKET_ID = "test_market"

# Base sizing strength
EDGE_SIZE_MULTIPLIER = 200.0

MODEL_PROBS = [0.60, 0.40, 0.535, 0.58, 0.50]

# -----------------------------
# Strategy controls
# -----------------------------

# Inverted signal discovered from your tests:
# bookmaker_prob > market_prob  -> BUY_NO
# bookmaker_prob < market_prob  -> BUY_YES
INVERT_SIGNAL = True

# Probability filter:
# only trade if market midpoint is inside this band
MIN_MARKET_PROB = 0.25
MAX_MARKET_PROB = 0.75

# Tiered edge sizing
# These are absolute edge buckets.
EDGE_TIER_1 = 0.013
EDGE_TIER_2 = 0.017
EDGE_TIER_3 = 0.019

# Multipliers by tier
TIER_1_MULTIPLIER = 1
TIER_2_MULTIPLIER = 1
TIER_3_MULTIPLIER = 1
