import os

from src.config_live import (
    STARTING_CASH,
    THRESHOLD,
    TRADE_SIZE,
    MAX_POSITION_SIZE,
    TAKE_PROFIT,
    STOP_LOSS,
    EDGE_SIZE_MULTIPLIER,
)
from src.data_loading_live import load_historical_data
from src.portfolio_live import create_portfolio, apply_fill, compute_portfolio_value
from src.signals_live import generate_signal
from src.risk_live import get_trade_decision
from src.execution_live import simulate_fill
from src.reporting_live import print_header, report_state, report_summary
from src.logging_live import initialize_csv_log, log_step_to_csv
from src.position_management_live import check_exit_conditions
from src.analysis_utils_live import log_run_metadata
from src.sizing_live import compute_trade_size
from src.validation_live import validate_portfolio_state


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_next_run_filepath(base_dir: str) -> str:
    logs_dir = os.path.join(base_dir, "data", "logs")
    os.makedirs(logs_dir, exist_ok=True)

    existing_files = os.listdir(logs_dir)
    run_numbers = []

    for filename in existing_files:
        if filename.startswith("run_") and filename.endswith(".csv"):
            try:
                number = int(filename.split("_")[1].split(".")[0])
                run_numbers.append(number)
            except ValueError:
                pass

    next_run_number = max(run_numbers, default=0) + 1
    return os.path.join(logs_dir, f"run_{next_run_number}.csv")


def run_simulation(
    threshold=None,
    take_profit=None,
    stop_loss=None,
    trade_size=None,
    edge_size_multiplier=None
):
    portfolio = create_portfolio(STARTING_CASH)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    TH = threshold if threshold is not None else THRESHOLD
    TP = take_profit if take_profit is not None else TAKE_PROFIT
    SL = stop_loss if stop_loss is not None else STOP_LOSS
    TS = trade_size if trade_size is not None else TRADE_SIZE
    ESM = edge_size_multiplier if edge_size_multiplier is not None else EDGE_SIZE_MULTIPLIER

    log_filepath = get_next_run_filepath(base_dir)
    initialize_csv_log(log_filepath)

    historical_filepath = os.path.join(
        base_dir,
        "src",
        "data",
        "historical",
        "historical_data.csv"
    )

    print("\n" + "=" * 60)
    print("DATA LOAD")
    print("=" * 60)
    print(f"Historical file: {historical_filepath}")

    historical_data = load_historical_data(historical_filepath)

    print(f"Rows loaded: {len(historical_data)}")
    if historical_data:
        first_timestamp, first_market, first_model_prob = historical_data[0]
        print("First row preview:")
        print(f"  timestamp   : {first_timestamp}")
        print(f"  market_id   : {first_market.market_id}")
        print(f"  best_bid    : {first_market.best_bid:.6f}")
        print(f"  best_ask    : {first_market.best_ask:.6f}")
        print(f"  model_prob  : {first_model_prob:.6f}")
    print("=" * 60)

    total_trades = 0
    buy_yes_count = 0
    buy_no_count = 0
    hold_count = 0
    risk_rejection_count = 0

    peak_value = STARTING_CASH
    max_drawdown = 0.0
    last_market = None

    for i, (timestamp, market, model_prob) in enumerate(historical_data):
        last_market = market
        print_header(f"Step {i + 1} | Time {timestamp}")
        print(f"MARKET ID: {market.market_id}")

        prev_value = compute_portfolio_value(portfolio, market)

        fill = None
        signal = None
        approved = False
        reason = "no decision yet"

        exit_triggered = False
        exit_reason = ""
        exit_side = ""
        realized_pnl = 0.0

        exit_triggered, exit_reason, exit_side, realized_pnl = check_exit_conditions(
            portfolio,
            market,
            TP,
            SL
        )

        if exit_triggered:
            print(f"EXIT TRIGGERED: {exit_reason}")
            approved = False
            reason = exit_reason
            validate_portfolio_state(portfolio)

        else:
            signal = generate_signal(market, model_prob, TH)
            approved, reason = get_trade_decision(signal, portfolio, MAX_POSITION_SIZE)

            print(f"SIGNAL: {signal.action} | APPROVED: {approved} | REASON: {reason}")

            if signal.action == "HOLD":
                hold_count += 1
            elif not approved:
                risk_rejection_count += 1

            if approved:
                dynamic_size = compute_trade_size(
                    signal=signal,
                    portfolio=portfolio,
                    max_position_size=MAX_POSITION_SIZE,
                    edge_size_multiplier=ESM
                )

                print(f"DYNAMIC SIZE: {dynamic_size:.3f}")

                if dynamic_size > 0:
                    fill = simulate_fill(signal, market, dynamic_size)

                    if fill is not None:
                        apply_fill(portfolio, fill, market)
                        validate_portfolio_state(portfolio)
                        total_trades += 1

                        if fill.side == "BUY_YES":
                            buy_yes_count += 1
                        elif fill.side == "BUY_NO":
                            buy_no_count += 1
                else:
                    print("DYNAMIC SIZE <= 0, no fill")
            else:
                print("TRADE NOT APPROVED")

        current_value = compute_portfolio_value(portfolio, market)
        step_pnl = current_value - prev_value

        if current_value > peak_value:
            peak_value = current_value

        drawdown = peak_value - current_value
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        validate_portfolio_state(portfolio)

        report_state(
            signal=signal,
            approved=approved,
            reason=reason,
            fill=fill,
            portfolio=portfolio,
            market=market,
            exit_triggered=exit_triggered,
            exit_reason=exit_reason,
            exit_side=exit_side,
            realized_pnl=realized_pnl,
            step_pnl=step_pnl
        )

        log_step_to_csv(
            log_filepath,
            i + 1,
            timestamp,
            signal,
            approved,
            reason,
            fill,
            portfolio,
            market,
            exit_triggered,
            exit_reason,
            exit_side,
            realized_pnl
        )

    final_value = (
        compute_portfolio_value(portfolio, last_market)
        if last_market is not None
        else STARTING_CASH
    )

    report_summary(
        total_trades,
        buy_yes_count,
        buy_no_count,
        hold_count,
        risk_rejection_count,
        peak_value,
        max_drawdown,
        final_value
    )

    log_run_metadata(
        os.path.join(base_dir, "data", "run_metadata.csv"),
        {
            "run_file": os.path.basename(log_filepath),
            "threshold": TH,
            "take_profit": TP,
            "stop_loss": SL,
            "trade_size": TS,
            "edge_size_multiplier": ESM
        }
    )


if __name__ == "__main__":
    run_simulation()