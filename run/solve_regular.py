import os
import sys
import pathlib
import json
import datetime
import pandas as pd
import argparse

if __name__=="__main__":
    base_folder = pathlib.Path()
    sys.path.append(str(base_folder / "../src"))
    from multi_period_dev import connect, get_my_data, prep_data, solve_multi_period_fpl
    import data_parser as pr

    with open('../data/regular_settings.json') as f:
        options = json.load(f)

        parser = argparse.ArgumentParser(add_help=False)
        for key in options.keys():
            if isinstance(options[key], (bool, list, dict)):
                continue

            parser.add_argument(f"--{key}", default=options[key], type=type(options[key]))

        args = parser.parse_known_args()[0]
        options = {**options, **vars(args)}

    if options.get("cbc_path") != "":
        os.environ['PATH'] += os.pathsep + options.get("cbc_path")

    if options.get("preseason"):
        my_data = {'picks': [], 'chips': [], 'transfers': {'limit': None, 'cost': 4, 'bank': 1000, 'value': 0}}
    elif options.get("use_login", False):
        session, team_id = connect()
        if session is None and team_id is None:
            exit(0)
    else:
        try:
            with open('../data/team.json') as f:
                my_data = json.load(f)
        except FileNotFoundError:
            print("Download your team data from https://fantasy.premierleague.com/api/my-team/YOUR-TEAM-ID/ and save it under data folder with name 'team.json'")
            exit(0)
    data = prep_data(my_data, options)

    response = solve_multi_period_fpl(data, options)
    for result in response:
        iter = result['iter']
        print(result['summary'])
        time_now = datetime.datetime.now()
        stamp = time_now.strftime("%Y-%m-%d_%H-%M-%S")
        if not (os.path.exists("../data/results/")):
            os.mkdir("../data/results/")
        result['picks'].to_csv(f"../data/results/regular_{stamp}_{iter}.csv")

    result_table = pd.DataFrame(response)
    print(result_table[['iter', 'sell', 'buy', 'score']])
