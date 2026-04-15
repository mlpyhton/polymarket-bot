import csv
import os
from datetime import datetime


def log_run_metadata(filepath, config):
    file_exists = os.path.exists(filepath)

    with open(filepath, mode="a", newline="") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "timestamp",
                "run_file",
                "threshold",
                "take_profit",
                "stop_loss",
                "trade_size",
                "edge_size_multiplier"
            ])

        writer.writerow([
            datetime.now().isoformat(),
            config["run_file"],
            config["threshold"],
            config["take_profit"],
            config["stop_loss"],
            config["trade_size"],
            config["edge_size_multiplier"]
        ])
