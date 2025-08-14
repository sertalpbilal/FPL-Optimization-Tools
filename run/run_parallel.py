import os
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
from solve import solve_regular

from utils import get_dict_combinations


def run_parallel_solves(chip_combinations, max_workers=None):
    if not max_workers:
        max_workers = os.cpu_count() - 2

    # these are added just to reduce the output, you can remove them or put any settings you want here
    options = {
        "verbose": False,
        "print_result_table": False,
        "print_decay_metrics": False,
        "print_transfer_chip_summary": False,
        "print_squads": False,
    }

    args = []
    for combination in chip_combinations:
        args.append({**options, **combination})

    # Use ProcessPoolExecutor to run commands in parallel
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(solve_regular, args))

    df = pd.concat(results).sort_values(by="score", ascending=False).reset_index(drop=True)
    df = df.drop("iter", axis=1)
    print(df)

    # you can save the results to a csv file if you want to, by uncommenting the line below
    df.to_csv("chip_solve.csv", encoding="utf-8", index=False)


if __name__ == "__main__":
    # edit the gameweeks you want to have chips available in here.
    # in this example it means it will run solves for 11 chips combinations:
    # no chips, bb1, bb2, fh2, fh3, fh4, bb1fh2, bb1fh3, bb1fh4, bb2fh3, bb2fh4
    # note that this is the 3 bb options multiplied by the 4 fh options, minus the invalid combination bb2fh2
    chip_gameweeks = {
        "use_bb": [None, 1, 2],
        "use_wc": [],
        "use_fh": [None, 2, 3, 4],
        "use_tc": [],
    }

    combinations = get_dict_combinations(chip_gameweeks)
    run_parallel_solves(combinations)
