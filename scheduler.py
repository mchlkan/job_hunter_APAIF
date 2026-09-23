import argparse
import time
import traceback
from datetime import datetime, timezone

import yaml

import run
import profiles.worker as worker


def run_once():
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"\n=== collection run @ {stamp} ===")
    try:
        run.main()
    except Exception:
        print("collection run failed:")
        traceback.print_exc()

    print(f"\n=== CV worker @ {stamp} ===")
    try:
        worker.main()
    except Exception:
        print("CV worker failed:")
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Loop the collection run and CV worker on an interval.")
    parser.add_argument("--once", action="store_true", help="run a single iteration and exit")
    args = parser.parse_args()

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    interval_minutes = config.get("schedule", {}).get("interval_minutes", 60)

    if args.once:
        run_once()
        return

    print(f"scheduler started, interval={interval_minutes}min (ctrl-c to stop)")
    while True:
        run_once()
        print(f"\nsleeping {interval_minutes}min...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    main()
