import os
import glob
import time
from concurrent.futures import ProcessPoolExecutor
import argparse
import json
from solve_regular import solve_regular


def load_settings(settings_path):
    with open(settings_path, "r") as f:
        settings = json.load(f)
    return settings


def run_sensitivity(options=None):

    if options is None or "count" not in options:
        print("Number of simulations and processes not provided.")
        return

    runs = options.get("count", 1)
    processes = options.get("processes", 1)

    start = time.time()

    all_jobs = [{"run_no": str(i + 1), "randomized": True} for i in range(runs)]

    with ProcessPoolExecutor(max_workers=processes) as executor:
        results = list(executor.map(solve_regular, all_jobs))

    end = time.time()

    print()
    print(f"Total time taken is {(end - start) / 60:.2f} minutes")


if __name__ == "__main__":
    try:
        # Parse command-line arguments
        parser = argparse.ArgumentParser(
            description="Run sensitivity analysis", allow_abbrev=False
        )
        parser.add_argument(
            "--settings_path",
            type=str,
            default="../data/regular_settings.json",
            help="Path to the JSON file containing regular settings",
        )
        parser.add_argument("--no", type=int, help="Number of simulations")
        parser.add_argument("--parallel", type=int, help="Number of parallel processes")
        args, unknown = parser.parse_known_args()

        # Load settings from regular_settings.json
        options = load_settings(args.settings_path)

        # Update settings with command line arguments
        if args.no:
            options["count"] = args.no
        if args.parallel:
            options["processes"] = args.parallel

    except Exception as e:
        print(f"Error: {e}")
        options = None

    run_sensitivity(options)
