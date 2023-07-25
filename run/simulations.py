import pandas as pd
import os
import glob
import time
from concurrent.futures import ProcessPoolExecutor
import argparse
from solve_regular import solve_regular

def run_sensitivity(options):

    if options is None or 'count' not in options:

        # print("Remember to delete results folder and enable noise! Also note: you may reach your results faster to run multiple tabs of this script")
        # print("")
        runs = int(input("How many simulations would you like to run? "))
        processes = int(input("How many processes you want to run in parallel? "))
    else:
        runs = options.get('count', 1)
        processes = options.get('processes', 1)

    start = time.time()

    # for i in range(runs):
    #     print('Run no: ' + str(i))
    #     os.system('python solve_regular.py --randomized true')

    all_jobs = [{'run_no': str(i+1), 'randomized': True} for i in range(runs)]

    with ProcessPoolExecutor(max_workers=processes) as executor:
        results = list(executor.map(solve_regular, all_jobs))

    end = time.time()

    print()
    print(f"Total time taken is {(end - start) / 60:.2f} minutes")

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Run sensitivity analysis")
        parser.add_argument("--no", type=int, help="Number of runs")
        args = parser.parse_args()
        options = {}
        if args.no:
            options['count'] = args.no
    except:
        options = None

    run_sensitivity(options)
