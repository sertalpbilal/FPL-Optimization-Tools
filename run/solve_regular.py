import os
import sys
import pathlib
import json
import datetime
import argparse

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--team", help = "json file from https://fantasy.premierleague.com/api/my-team/MY_TEAM_ID/")
    parser.add_argument("-s", "--settings", help = "json settings file as described here https://github.com/prmac/FPL-Optimization-Tools/blob/main/run/regular_settings.json")
    parser.add_argument("-p", "--projections", help = "csv file of projections downloaded from FPLReview")

    args = parser.parse_args()
    team = Path(args.team)
    settings = Path(args.settings)
    projections = Path(args.projections)
    
    base_folder = pathlib.Path()
    sys.path.append(str(base_folder / "../src"))
    from multi_period_dev import connect, get_my_data, prep_data, solve_multi_period_fpl

    with open(settings) as f:
        options = json.load(f)

    if options.get("cbc_path") != "":
        os.environ['PATH'] += os.pathsep + options.get("cbc_path")

    if options.get("preseason"):
        my_data = {'picks': [], 'chips': [], 'transfers': {'limit': None, 'cost': 4, 'bank': 1000, 'value': 0}}
    elif options.get("use_login", False):
        session, team_id = connect()
        if session is None and team_id is None:
            exit(0)
    else:
        with open(team) as f:
            my_data = json.load(f)
    data = prep_data(my_data, options)

    result = solve_multi_period_fpl(data, options)
    print(result['summary'])
    time_now = datetime.datetime.now()
    stamp = time_now.strftime("%Y-%m-%d_%H-%M-%S")
    result['picks'].to_csv(f"results/regular_{stamp}.csv")
