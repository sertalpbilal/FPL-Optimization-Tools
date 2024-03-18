import os
import sys
import pathlib
import json
import datetime
import pandas as pd
import argparse
import random
import string


def get_random_id(n):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def solve_regular(runtime_options=None):

    try:
        import google.colab
        is_colab = True
    except:
        is_colab = False

    base_folder = pathlib.Path()
    sys.path.append(str(base_folder / "../src"))
    from multi_period_dev import connect, get_my_data, prep_data, solve_multi_period_fpl, generate_team_json
    import data_parser as pr

    if is_colab:
        # Read options from the file
        with open('settings.json') as f:
            options = json.load(f)

    else:
        # Read options from the file
        with open('../data/regular_settings.json') as f:
            options = json.load(f)

    parser = argparse.ArgumentParser(add_help=False)
    for key in options.keys():
        if isinstance(options[key], (list, dict)):
            continue

        parser.add_argument(f"--{key}", default=options[key], type=type(options[key]))

    args = parser.parse_known_args()[0]
    options = {**options, **vars(args)}
    
    if runtime_options is not None:
        options = {**options, **runtime_options}

    if options.get("cbc_path") != "" and options.get("cbc_path") is not None:
        os.environ['PATH'] += os.pathsep + options.get("cbc_path")

    if options.get("preseason"):
        my_data = {'picks': [], 'chips': [], 'transfers': {'limit': None, 'cost': 4, 'bank': 1000, 'value': 0}}
    elif options.get("use_login", False):
        session, team_id = connect()
        if session is None and team_id is None:
            exit(0)
    else:
        if options.get("team_data", "json").lower() == "id":
            team_id = options.get("team_id", None)
            if team_id is None:
                print("You must supply your team_id in data/regular_settings.json")
                exit(0)
            my_data = generate_team_json(team_id)
        else:
            try:
                with open('../data/team.json') as f:
                    my_data = json.load(f)
            except FileNotFoundError:
                print(
                    """You must either:
                        1. Download your team data from https://fantasy.premierleague.com/api/my-team/YOUR-TEAM-ID/ and
                            save it under data folder with name 'team.json', or
                        2. Set "team_data" in regular_settings to "ID", and set the "team_id" value to your team's ID
                    """)
                exit(0)
    data = prep_data(my_data, options)

    response = solve_multi_period_fpl(data, options)
    run_id = get_random_id(5)
    for result in response:
        iter = result['iter']
        print(result['summary'])
        time_now = datetime.datetime.now()
        stamp = time_now.strftime("%Y-%m-%d_%H-%M-%S")
        if not (os.path.exists("../data/results/")):
            os.mkdir("../data/results/")
        result['picks'].to_csv(f"../data/results/regular_{stamp}_{run_id}_{iter}.csv")

    print("Result Summary")
    result_table = pd.DataFrame(response)
    print(result_table[['iter', 'sell', 'buy', 'chip', 'score']])

    if len(options.get('report_decay_base', [])) > 0:
        try:
            print("Decay Metrics")
            metrics_df = pd.DataFrame([{'iter': result['iter'], **result['decay_metrics']} for result in response])
            print(metrics_df)
    
            # print("Difference to Best")
            # metrics_diff_df = metrics_df.copy()
            # keys = list(response[0]['decay_metrics'].keys())
            # metrics_diff_df[keys] = metrics_diff_df[keys] - metrics_diff_df[keys].max(axis=0)
            # print(metrics_diff_df)
        except:
            pass

    # Detailed print
    for result in response:
        picks = result['picks']
        gws = picks['week'].unique()
        print(f"Solution {result['iter']+1}")
        for gw in gws:
            line_text = ''
            chip_text = picks[picks['week']==gw].iloc[0]['chip']
            if chip_text != '':
                line_text += '(' + chip_text + ') '
            sell_text = ', '.join(picks[(picks['week'] == gw) & (picks['transfer_out'] == 1)]['name'].to_list())
            buy_text = ', '.join(picks[(picks['week'] == gw) & (picks['transfer_in'] == 1)]['name'].to_list())
            if sell_text != '':
                line_text += sell_text + ' -> ' + buy_text
            else:
                line_text += "Roll"
            print(f"\tGW{gw}: {line_text}")


    # Link to FPL.Team
    get_fplteam_link(options, response)


def get_fplteam_link(options, response):
    
    print("\nYou can see the solutions on a planner using the following FPL.Team links:")
    team_id = options.get('team_id', 1)
    if options.get('team_id') is None:
        print("(Do not forget to add your team ID to regular_settings.json file to get a custom link.)")
    url_base = f"https://fpl.team/plan/{team_id}/?"
    for result in response:
        result_url = url_base
        picks = result['picks']
        gws = picks['week'].unique()
        for gw in gws:
            lineup_players = ",".join(picks[(picks['week']==gw)&(picks['lineup']>0.5)]['id'].astype(str).to_list())
            bench_players = ",".join(picks[(picks['week']==gw)&(picks['bench']>-0.5)]['id'].astype(str).to_list())
            cap = picks[(picks['week']==gw)&(picks['captain']>0.5)].iloc[0]['id']
            vcap = picks[(picks['week']==gw)&(picks['vicecaptain']>0.5)].iloc[0]['id']
            chip = picks[picks['week']==gw].iloc[0]['chip']
            sold_players = picks[(picks['week'] == gw) & (picks['transfer_out'] > 0.5)].sort_values(by='type')['id'].astype(str).to_list()
            bought_players = picks[(picks['week'] == gw) & (picks['transfer_in'] > 0.5)].sort_values(by='type')['id'].astype(str).to_list()
            
            if gw == 1:
                sold_players = []
                bought_players = []
            
            tr_string = ';'.join([f"{i},{j}" for (i,j) in zip (sold_players, bought_players)])
            
            if tr_string == '':
                tr_string = ';'

            sub_text = ''
            if gw == 1:
                sub_text = ';'
            else:
                prev_lineup = picks[(picks['week'] == gw-1) & (picks['lineup'] > 0.5)].sort_values(by='type')['id'].astype(str).to_list()
                now_bench = picks[(picks['week'] == gw) & (picks['bench'] > -0.5)].sort_values(by='type')['id'].astype(str).to_list()
                lineup_to_bench = [i for i in prev_lineup if i in now_bench]
                prev_bench = picks[(picks['week'] == gw-1) & (picks['bench'] > -0.5)].sort_values(by='type')['id'].astype(str).to_list()
                now_lineup = picks[(picks['week'] == gw) & (picks['lineup'] > 0.5)].sort_values(by='type')['id'].astype(str).to_list()
                bench_to_lineup = [i for i in prev_bench if i in now_lineup]
                sub_text = ';'.join([f"{i},{j}" for (i,j) in zip (lineup_to_bench, bench_to_lineup)])
                
                if sub_text == '':
                    sub_text = ';'

            gw_params = f'lineup{gw}={lineup_players}&bench{gw}={bench_players}&cap{gw}={cap}&vcap{gw}={vcap}&chip{gw}={chip}&transfers{gw}={tr_string}&subs{gw}={sub_text}&opt=true'
            result_url += ("" if gw == gws[0] else "&") + gw_params
        print(f"Solution {result['iter']+1}: {result_url}")



if __name__ == "__main__":
    solve_regular()
