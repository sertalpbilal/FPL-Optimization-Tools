import pandas as pd
import os
import glob
import time
from concurrent.futures import ProcessPoolExecutor
import argparse
from solve_regular import solve_regular
import json

def run_sensitivity(options=None):

    if options is None or 'count' not in options:

        # print("Remember to delete results folder and enable noise! Also note: you may reach your results faster to run multiple tabs of this script")
        # print("")
        runs = int(input("How many simulations would you like to run? "))
        processes = int(input("How many processes you want to run in parallel? "))
        use_binaries = input("Use binaries (y or n)? ")
    else:
        runs = options.get('count', 1)
        processes = options.get('processes', 1)
        use_binaries = options.get('use_binaries', 'n')

    # if use_binaries is set loop through binary_files dict in regular_settings and set number of sim run for each binary based on provided weights
    if use_binaries.lower() == 'y':
        print("Using binary config for simulations")
        with open('../data/regular_settings.json') as f:
            settings = json.load(f)

        # if generate_binary_files is set to true, generate binary files based on fixture configs
        if settings.get("generate_binary_files"):
            print("Generating binary files")
            from binary_file_generator import generate_binary_files

            file_path = '../data/fplreview_original.csv'
            generate_binary_files(file_path, settings)

        # get total weights for configured binary files for scaling up weights to add up to 1
        total_weights = sum([config.get("weight") for config in settings.get("binary_files").values()])
        
        for binary, config in settings.get("binary_files").items():
            scaled_weight = (config.get("weight") / total_weights)
            print(f"Binary file {binary} weight scaled from {config.get("weight")} to {scaled_weight:.2f}") 
            weighted_runs = round(scaled_weight * runs)    

            print(f"Running {weighted_runs} simulations for binary file {binary}")

            start = time.time()

            all_jobs = [{'run_no': str(i+1), 'randomized': True, 'binary_file_name': binary.rstrip('.csv')} for i in range(weighted_runs)]

            with ProcessPoolExecutor(max_workers=processes) as executor:
                results = list(executor.map(solve_regular, all_jobs))

            end = time.time()

            print()
            print(f"Total time taken is {(end - start) / 60:.2f} minutes")    
    else:
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
        parser.add_argument("--parallel", type=int, help="Number of parallel runs")
        parser.add_argument("--use_binaries", type=str, help="Do you want to use binaries? (y/n)")
        args = parser.parse_args()
        options = {}
        if args.no:
            options['count'] = args.no
        if args.parallel:
            options['processes'] = args.parallel
        if args.use_binaries:
            options['use_binaries'] = args.use_binaries
    except:
        options = None

    run_sensitivity(options)
