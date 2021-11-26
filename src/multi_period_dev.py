import pandas as pd
import numpy as np
import sasoptpy as so
import requests
import os
import time
from subprocess import Popen, DEVNULL
from pathlib import Path
import json
from requests import Session
import random
import string


def get_random_id(n):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def xmin_to_prob(xmin, sub_on=0.5, sub_off=0.3):
    start = min( max ( (xmin - 25 * sub_on) / (90 * (1-sub_off) + 65 * sub_off - 25 * sub_on), 0.001), 0.999)
    return start + (1-start) * sub_on

# def solve_standard_problem():
#     r = solve_multi_period_fpl(team_id=7331, gw=4, ft=1, horizon=3, objective='regular')
#     print(r['picks'])
#     print(r['summary'])
#     r['picks'].to_csv('optimal_plan_regular.csv')
    
#     # r = solve_multi_period_fpl(team_id=7331, gw=3, ft=2, horizon=3, objective='decay', decay_base=0.84)
#     # print(r['picks'])
#     # print(r['summary'])
#     # r['picks'].to_csv('optimal_plan_decay.csv')


# def solve_autobench_problem():
#     r = solve_multi_period_fpl(team_id=7331, gw=4, ft=1, horizon=3, objective='regular')
#     print(r['picks'])
#     print(r['summary'])
#     r['picks'].to_csv('optimal_plan_regular_stage_1.csv')

#     df = r['picks']
#     lineup_gk = df[(df['week'] == 4) & (df['pos'] == 'GKP') & (df['lineup'] == 1)]
#     lineup_gk = lineup_gk.iloc[0]
#     lineup_gk_mins = lineup_gk['xMin']
#     gk_autosub_prob = xmin_to_prob(lineup_gk_mins, sub_on=0, sub_off=0)
#     gk_weight = 1-gk_autosub_prob

#     field_players = df[(df['week'] == 4) & (df['pos'] != 'GKP') & (df['lineup'] == 1)]
#     field_players_xmins = field_players['xMin'].tolist()
#     field_players_probs = [xmin_to_prob(i) for i in field_players_xmins]

#     prob = 1
#     for i in field_players_probs:
#         prob *= i
#     bench_1_weight = 1 - prob

#     bench_weights = {0: gk_weight, 1: bench_1_weight, 2: 0.06, 3: 0.002}
#     r = solve_multi_period_fpl(team_id=7331, gw=4, ft=1, horizon=3, objective='regular', bench_weights=bench_weights)
#     print(r['picks'])
#     print(r['summary'])
#     r['picks'].to_csv('optimal_plan_regular_stage_2.csv')


# def solve_randomized_problem():
#     r = solve_multi_period_fpl(team_id=7331, gw=5, ft=1, horizon=3, objective='regular', seed=None, randomized=True)
#     print(r['picks'])
#     print(r['summary'])
#     r['picks'].to_csv('optimal_plan_randomized.csv')


def connect():
    base_folder = Path()
    with open(base_folder / "../data/login.json") as f:
        credentials = json.load(f)
    session = Session()
    payload = {
        'password': credentials['password'],
        'login': credentials['email'],
        'redirect_uri': 'https://fantasy.premierleague.com/a/login',
        'app': 'plfpl-web'
    }
    session.post('https://users.premierleague.com/accounts/login/', payload)
    r = session.get('https://fantasy.premierleague.com/api/me/')
    if r.status_code != 200:
        raise ValueError('Cannot read data')
    return [session, r.json()['player']['entry']]


def get_my_data(session, team_id):
    r = session.get(f"https://fantasy.premierleague.com/api/my-team/{team_id}/")
    d = r.json()
    d['team_id'] = team_id
    return d


def prep_data(my_data, options):
    r = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
    fpl_data = r.json()

    gw = 0
    for e in fpl_data['events']:
        if e['is_next']:
            gw = e['id']
            break

    horizon = options.get('horizon', 3)

    element_data = pd.DataFrame(fpl_data['elements'])
    team_data = pd.DataFrame(fpl_data['teams'])
    elements_team = pd.merge(element_data, team_data, left_on='team', right_on='id')
    review_data = pd.read_csv('../data/fplreview.csv')
    review_data = review_data.fillna(0)
    review_data['review_id'] = review_data.index+1
    merged_data = pd.merge(elements_team, review_data, left_on='id_x', right_on='review_id')
    merged_data.set_index(['id_x'], inplace=True)

    original_keys = merged_data.columns.to_list()
    keys = [k for k in original_keys if "_Pts" in k]
    min_keys = [k for k in original_keys if "_xMins" in k]
    merged_data['total_ev'] = merged_data[keys].sum(axis=1)
    merged_data['total_min'] = merged_data[min_keys].sum(axis=1)

    merged_data.sort_values(by=['total_ev'], ascending=[False], inplace=True)

    # Filter players by xMin
    initial_squad = [int(i['element']) for i in my_data['picks']]
    # safe_players = initial_squad + 
    xmin_lb = options.get('xmin_lb', 1)
    print(len(merged_data), "total players (before)")
    merged_data = merged_data[(merged_data['total_min'] >= xmin_lb) | (merged_data['review_id'].isin(initial_squad))].copy()
    print(len(merged_data), "total players (after)")

    if options.get('randomized', False):
        rng = np.random.default_rng(seed = options.get('seed'))
        gws = list(range(gw, min(39, gw+horizon)))
        for w in gws:
            noise = merged_data[f"{w}_Pts"] * (92 - merged_data[f"{w}_xMins"]) / 134 * rng.standard_normal(size=len(merged_data))
            merged_data[f"{w}_Pts"] = merged_data[f"{w}_Pts"] + noise

    type_data = pd.DataFrame(fpl_data['element_types']).set_index(['id'])

    buy_price = (merged_data['now_cost']/10).to_dict()
    sell_price = {i['element']: i['selling_price']/10 for i in my_data['picks']}
    price_modified_players = []
    for i in my_data['picks']:
        if buy_price[i['element']] != sell_price[i['element']]:
            price_modified_players.append(i['element'])
            print(f"Added player {i['element']} to list, buy price {buy_price[i['element']]} sell price {sell_price[i['element']]}")



    itb = my_data['transfers']['bank']/10
    ft = my_data['transfers']['limit'] - my_data['transfers']['made']
    if ft < 0:
        ft = 0
    # If wildcard is active, then you have: "status_for_entry": "active" under my_data['chips']
    for c in my_data['chips']:
        if c['name'] == 'wildcard' and c['status_for_entry'] == 'active':
            ft = 1
            options['use_wc'] = gw
            break

    return {
        'merged_data': merged_data,
        'team_data': team_data,
        'my_data': my_data,
        'type_data': type_data,
        'next_gw': gw,
        'initial_squad': initial_squad,
        'sell_price': sell_price,
        'buy_price': buy_price,
        'price_modified_players': price_modified_players,
        'itb': itb,
        'ft': ft
        }




def solve_multi_period_fpl(data, options):
    """
    Solves multi-objective FPL problem with transfers

    Parameters
    ----------
    data: dict
        Pre-processed data for the problem definition
    options: dict
        User controlled values for the problem instance
    """

    # Arguments
    problem_id = get_random_id(5)
    horizon = options.get('horizon', 3)
    objective = options.get('objective', 'regular')
    decay_base = options.get('decay_base', 0.84)
    bench_weights = options.get('bench_weights', {0: 0.03, 1: 0.21, 2: 0.06, 3: 0.002})
    wc_limit = options.get('wc_limit', 0)
    ft_value = options.get('ft_value', 1.5)
    itb_value = options.get('itb_value', 0.08)
    ft = data.get('ft', 1)
    if ft <= 0:
        ft = 0

    # Data
    problem_name = f'mp_h{horizon}_regular' if objective == 'regular' else f'mp_h{horizon}_o{objective[0]}_d{decay_base}'
    merged_data = data['merged_data']
    team_data = data['team_data']
    type_data = data['type_data']
    next_gw = data['next_gw']
    initial_squad = data['initial_squad']
    itb = data['itb']

    # Sets
    players = merged_data.index.to_list()
    element_types = type_data.index.to_list()
    teams = team_data['name'].to_list()
    gameweeks = list(range(next_gw, next_gw+horizon))
    all_gw = [next_gw-1] + gameweeks
    order = [0, 1, 2, 3]
    price_modified_players = data['price_modified_players']

    # Model
    model = so.Model(name=problem_name)

    # Variables
    squad = model.add_variables(players, all_gw, name='squad', vartype=so.binary)
    lineup = model.add_variables(players, gameweeks, name='lineup', vartype=so.binary)
    captain = model.add_variables(players, gameweeks, name='captain', vartype=so.binary)
    vicecap = model.add_variables(players, gameweeks, name='vicecap', vartype=so.binary)
    bench = model.add_variables(players, gameweeks, order, name='bench', vartype=so.binary)
    transfer_in = model.add_variables(players, gameweeks, name='transfer_in', vartype=so.binary)
    # transfer_out = model.add_variables(players, gameweeks, name='transfer_out', vartype=so.binary)
    transfer_out_first = model.add_variables(price_modified_players, gameweeks, name='tr_out_first', vartype=so.binary)
    transfer_out_regular = model.add_variables(players, gameweeks, name='tr_out_reg', vartype=so.binary)
    transfer_out = {
        (p,w): transfer_out_regular[p,w] + (transfer_out_first[p,w] if p in price_modified_players else 0) for p in players for w in gameweeks
    }
    in_the_bank = model.add_variables(all_gw, name='itb', vartype=so.continuous, lb=0)
    free_transfers = model.add_variables(all_gw, name='ft', vartype=so.integer, lb=0, ub=2)
    # Add a constraint for future transfers to be between 1 and 2
    penalized_transfers = model.add_variables(gameweeks, name='pt', vartype=so.integer, lb=0)
    aux = model.add_variables(gameweeks, name='aux', vartype=so.binary)
    use_wc = model.add_variables(gameweeks, name='use_wc', vartype=so.binary)

    # Dictionaries
    lineup_type_count = {(t,w): so.expr_sum(lineup[p,w] for p in players if merged_data.loc[p, 'element_type'] == t) for t in element_types for w in gameweeks}
    squad_type_count = {(t,w): so.expr_sum(squad[p,w] for p in players if merged_data.loc[p, 'element_type'] == t) for t in element_types for w in gameweeks}
    player_type = merged_data['element_type'].to_dict()
    # player_price = (merged_data['now_cost'] / 10).to_dict()
    sell_price = data['sell_price']
    buy_price = data['buy_price']
    sold_amount = {w: 
        so.expr_sum(sell_price[p] * transfer_out_first[p,w] for p in price_modified_players) +\
        so.expr_sum(buy_price[p] * transfer_out_regular[p,w] for p in players)
        for w in gameweeks}
    bought_amount = {w: so.expr_sum(buy_price[p] * transfer_in[p,w] for p in players) for w in gameweeks}
    points_player_week = {(p,w): merged_data.loc[p, f'{w}_Pts'] for p in players for w in gameweeks}
    minutes_player_week = {(p,w): merged_data.loc[p, f'{w}_xMins'] for p in players for w in gameweeks}
    squad_count = {w: so.expr_sum(squad[p, w] for p in players) for w in gameweeks}
    number_of_transfers = {w: so.expr_sum(transfer_out[p,w] for p in players) for w in gameweeks}
    number_of_transfers[next_gw-1] = 1
    transfer_diff = {w: number_of_transfers[w] - free_transfers[w] - 15 * use_wc[w] for w in gameweeks}

    # Initial conditions
    model.add_constraints((squad[p, next_gw-1] == 1 for p in initial_squad), name='initial_squad_players')
    model.add_constraints((squad[p, next_gw-1] == 0 for p in players if p not in initial_squad), name='initial_squad_others')
    model.add_constraint(in_the_bank[next_gw-1] == itb, name='initial_itb')
    model.add_constraint(free_transfers[next_gw] == ft, name='initial_ft')
    model.add_constraints((free_transfers[w] >= 1 for w in gameweeks if w > next_gw), name='future_ft_limit')

    # Constraints
    model.add_constraints((squad_count[w] == 15 for w in gameweeks), name='squad_count')
    model.add_constraints((so.expr_sum(lineup[p,w] for p in players) == 11 for w in gameweeks), name='lineup_count')
    model.add_constraints((so.expr_sum(bench[p,w,0] for p in players if player_type[p] == 1) == 1 for w in gameweeks), name='bench_gk')
    model.add_constraints((so.expr_sum(bench[p,w,o] for p in players) == 1 for w in gameweeks for o in [1,2,3]), name='bench_count')
    model.add_constraints((so.expr_sum(captain[p,w] for p in players) == 1 for w in gameweeks), name='captain_count')
    model.add_constraints((so.expr_sum(vicecap[p,w] for p in players) == 1 for w in gameweeks), name='vicecap_count')
    model.add_constraints((lineup[p,w] <= squad[p,w] for p in players for w in gameweeks), name='lineup_squad_rel')
    model.add_constraints((bench[p,w,o] <= squad[p,w] for p in players for w in gameweeks for o in order), name='bench_squad_rel')
    model.add_constraints((captain[p,w] <= lineup[p,w] for p in players for w in gameweeks), name='captain_lineup_rel')
    model.add_constraints((vicecap[p,w] <= lineup[p,w] for p in players for w in gameweeks), name='vicecap_lineup_rel')
    model.add_constraints((captain[p,w] + vicecap[p,w] <= 1 for p in players for w in gameweeks), name='cap_vc_rel')
    model.add_constraints((lineup[p,w] + so.expr_sum(bench[p,w,o] for o in order) <= 1 for p in players for w in gameweeks), name='lineup_bench_rel')
    model.add_constraints((lineup_type_count[t,w] == [type_data.loc[t, 'squad_min_play'], type_data.loc[t, 'squad_max_play']] for t in element_types for w in gameweeks), name='valid_formation')
    model.add_constraints((squad_type_count[t,w] == type_data.loc[t, 'squad_select'] for t in element_types for w in gameweeks), name='valid_squad')
    model.add_constraints((so.expr_sum(squad[p,w] for p in players if merged_data.loc[p, 'name'] == t) <= 3 for t in teams for w in gameweeks), name='team_limit')
    ## Transfer constraints
    model.add_constraints((squad[p,w] == squad[p,w-1] + transfer_in[p,w] - transfer_out[p,w] for p in players for w in gameweeks), name='squad_transfer_rel')
    model.add_constraints((in_the_bank[w] == in_the_bank[w-1] + sold_amount[w] - bought_amount[w] for w in gameweeks), name='cont_budget')
    ## Free transfer constraints
    model.add_constraints((free_transfers[w] == aux[w] + 1 for w in gameweeks if w > next_gw), name='aux_ft_rel')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] - 2 * use_wc[w] <= 2 * aux[w] for w in gameweeks if w > next_gw), name='force_aux_1')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] - 2 * use_wc[w] >= aux[w] + (-14)*(1-aux[w]) for w in gameweeks if w > next_gw), name='force_aux_2')
    model.add_constraints((penalized_transfers[w] >= transfer_diff[w] for w in gameweeks), name='pen_transfer_rel')
    ## Chip constraints
    model.add_constraint(so.expr_sum(use_wc[w] for w in gameweeks) <= wc_limit, name='use_wc_limit')
    model.add_constraints((aux[w] <= 1-use_wc[w-1] for w in gameweeks if w > next_gw), name='ft_after_wc')
    if options.get('use_wc', None) is not None:
        model.add_constraint(use_wc[options['use_wc']] == 1, name='force_wc')

    ## Multiple-sell fix
    model.add_constraints((transfer_out_first[p,w] + transfer_out_regular[p,w] <= 1 for p in price_modified_players for w in gameweeks), name='multi_sell_1')
    model.add_constraints((
        (wbar - next_gw + 1) * so.expr_sum(transfer_out_first[p,w] for w in gameweeks if w >= wbar) >=
        so.expr_sum(transfer_out_regular[p,w] for w in gameweeks if w >= wbar)
        for p in price_modified_players for wbar in gameweeks
    ), name='multi_sell_2')
    model.add_constraints((so.expr_sum(transfer_out_first[p,w] for w in gameweeks) <= 1 for p in price_modified_players), name='multi_sell_3')

    
    ## Optional constraints
    if options.get('banned', None) is not None:
        banned_players = options['banned']
        model.add_constraints((so.expr_sum(squad[p,w] for w in gameweeks) == 0 for p in banned_players), name='ban_player')

    if options.get('locked', None) is not None:
        locked_players = options['locked']
        model.add_constraints((squad[p,w] == 1 for p in locked_players for w in gameweeks), name='lock_player')

    if options.get("no_future_transfer"):
        model.add_constraint(so.expr_sum(transfer_in[p,w] for p in players for w in gameweeks if w > next_gw and w != options.get('use_wc')) == 0, name='no_future_transfer')

    # Objectives
    gw_xp = {w: so.expr_sum(points_player_week[p,w] * (lineup[p,w] + captain[p,w] + 0.1*vicecap[p,w] + so.expr_sum(bench_weights[o] * bench[p,w,o] for o in order)) for p in players) for w in gameweeks}
    gw_total = {w: gw_xp[w] - 4 * penalized_transfers[w] + ft_value * free_transfers[w] + itb_value * in_the_bank[w] for w in gameweeks}
    if objective == 'regular':
        total_xp = so.expr_sum(gw_total[w] for w in gameweeks)
        model.set_objective(-total_xp, sense='N', name='total_regular_xp')
    else:
        decay_objective = so.expr_sum(gw_total[w] * pow(decay_base, w-next_gw) for w in gameweeks)
        model.set_objective(-decay_objective, sense='N', name='total_decay_xp')

    # Solve
    tmp_folder = Path() / "tmp"
    tmp_folder.mkdir(exist_ok=True, parents=True)
    model.export_mps(f'tmp/{problem_name}_{problem_id}.mps')
    print(f"Exported problem with name: {problem_name}_{problem_id}")

    t0 = time.time()
    time.sleep(0.5)

    use_cmd = options.get('use_cmd', False)

    command = f'cbc tmp/{problem_name}_{problem_id}.mps cost column ratio 1 solve solu tmp/{problem_name}_{problem_id}_sol_init.txt'
    if use_cmd:
        os.system(command)
    else:
        process = Popen(command, shell=False)
        process.wait()
    secs = options.get('secs', 20*60)
    command = f'cbc tmp/{problem_name}_{problem_id}.mps mips tmp/{problem_name}_{problem_id}_sol_init.txt cost column sec {secs} solve solu tmp/{problem_name}_{problem_id}_sol.txt'
    if use_cmd:
        os.system(command)
    else:
        process = Popen(command, shell=False) # add 'stdout=DEVNULL' for disabling logs
        process.wait()

    t1 = time.time()
    print(t1-t0, "seconds passed")

    # Parsing
    with open(f'tmp/{problem_name}_{problem_id}_sol.txt', 'r') as f:
        for line in f:
            if 'objective value' in line:
                continue
            words = line.split()
            var = model.get_variable(words[1])
            var.set_value(float(words[2]))

    # DataFrame generation
    picks = []
    for w in gameweeks:
        for p in players:
            if squad[p,w].get_value() + transfer_out[p,w].get_value() > 0.5:
                lp = merged_data.loc[p]
                is_captain = 1 if captain[p,w].get_value() > 0.5 else 0
                is_squad = 1 if squad[p,w].get_value() > 0.5 else 0
                is_lineup = 1 if lineup[p,w].get_value() > 0.5 else 0
                is_vice = 1 if vicecap[p,w].get_value() > 0.5 else 0
                is_transfer_in = 1 if transfer_in[p,w].get_value() > 0.5 else 0
                is_transfer_out = 1 if transfer_out[p,w].get_value() > 0.5 else 0
                bench_value = -1
                for o in order:
                    if bench[p,w,o].get_value() > 0.5:
                        bench_value = o
                position = type_data.loc[lp['element_type'], 'singular_name_short']
                player_buy_price = 0 if not is_transfer_in else buy_price[p]
                player_sell_price = 0 if not is_transfer_out else (sell_price[p] if p in price_modified_players and transfer_out_first[p,w].get_value() > 0.5 else buy_price[p])
                picks.append([
                    w, lp['web_name'], position, lp['element_type'], lp['name'], player_buy_price, player_sell_price, round(points_player_week[p,w],2), minutes_player_week[p,w], is_squad, is_lineup, bench_value, is_captain, is_vice, is_transfer_in, is_transfer_out
                ])

    picks_df = pd.DataFrame(picks, columns=['week', 'name', 'pos', 'type', 'team', 'buy_price', 'sell_price', 'xP', 'xMin', 'squad', 'lineup', 'bench', 'captain', 'vicecaptain', 'transfer_in', 'transfer_out']).sort_values(by=['week', 'lineup', 'type', 'xP'], ascending=[True, False, True, True])
    total_xp = so.expr_sum((lineup[p,w] + captain[p,w]) * points_player_week[p,w] for p in players for w in gameweeks).get_value()

    picks_df.sort_values(by=['week', 'squad', 'lineup', 'bench', 'type'], ascending=[True, False, False, True, True], inplace=True)

    # Writing summary
    summary_of_actions = ""
    for w in gameweeks:
        summary_of_actions += f"** GW {w}:\n"
        summary_of_actions += f"ITB={in_the_bank[w].get_value()}, FT={free_transfers[w].get_value()}, PT={penalized_transfers[w].get_value()}, NT={number_of_transfers[w].get_value()}\n"
        for p in players:
            if transfer_in[p,w].get_value() > 0.5:
                summary_of_actions += f"Buy {p} - {merged_data['web_name'][p]}\n"
        for p in players:
            if transfer_out[p,w].get_value() > 0.5:
                summary_of_actions += f"Sell {p} - {merged_data['web_name'][p]}\n"

    if options.get('delete_tmp'):
        os.unlink(f"tmp/{problem_name}_{problem_id}.mps")
        os.unlink(f"tmp/{problem_name}_{problem_id}_sol.txt")

    return {'model': model, 'picks': picks_df, 'total_xp': total_xp, 'summary': summary_of_actions}




if __name__ == '__main__':

    t0 = time.time()

    options = {
        'horizon': 3,
        'randomized': False,
        # 'seed': 42
        # 'use_wc': 8,
        'wc_limit': 0,
        'banned': [],
        'xmin_lb': 0
    }

    session, team_id = connect()
    my_data = get_my_data(session, team_id)
    data = prep_data(my_data, options)
    result = solve_multi_period_fpl(data, options)

    final_time = time.time()
    print(final_time - t0, "seconds passed in total")

    # You can change "use_wc" to another GW if you haven't activated your WC
    if False:
        options['use_wc'] = 12
        data = prep_data(my_data, options)
        result = solve_multi_period_fpl(data, options)
        print(result['summary'])
        result['picks'].to_csv("gw12_wildcard.csv")


    # solve_standard_problem() # Episode 3 & 5
    # solve_autobench_problem() # Episode 6
    # solve_randomized_problem() # Episode 7

