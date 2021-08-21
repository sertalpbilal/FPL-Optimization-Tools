import pandas as pd
import sasoptpy as so
import requests
import os
import time
import random
import string
from subprocess import Popen, DEVNULL
import pathlib
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
import itertools

def get_data(team_id, gw):
    r = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
    fpl_data = r.json()
    element_data = pd.DataFrame(fpl_data['elements'])
    team_data = pd.DataFrame(fpl_data['teams'])
    elements_team = pd.merge(element_data, team_data, left_on='team', right_on='id')
    review_data = pd.read_csv('../data/fplreview.csv')
    review_data = review_data.fillna(0)
    review_data['review_id'] = review_data.index+1
    merged_data = pd.merge(elements_team, review_data, left_on='id_x', right_on='review_id')
    merged_data.set_index(['id_x'], inplace=True)
    next_gw = int(review_data.keys()[5].split('_')[0])
    type_data = pd.DataFrame(fpl_data['element_types']).set_index(['id'])

    r = requests.get(f'https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/')
    picks_data = r.json()
    initial_squad = [i['element'] for i in picks_data['picks']]
    r = requests.get(f'https://fantasy.premierleague.com/api/entry/{team_id}/')
    general_data = r.json()
    itb = general_data['last_deadline_bank'] / 10

    return {'merged_data': merged_data, 'team_data': team_data, 'type_data': type_data, 'next_gw': next_gw, 'initial_squad': initial_squad, 'itb': itb}


def get_transfer_history(team_id, last_gw):
    transfers = []
    # Reversing GW history until a chip is played or 2+ transfers were made
    for gw in range(last_gw, 0, -1):
        res = requests.get(f'https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/').json()
        transfer = res['entry_history']['event_transfers']
        chip = res['active_chip']

        transfers.append(transfer)
        if transfer > 1 or (chip is not None and (chip != '3xc' or chip != 'bboost')):
            break

    return transfers


def get_rolling(team_id, last_gw):
    transfers = get_transfer_history(team_id, last_gw)

    # Start from gw where last chip used or when hits were taken
    # Reset FT count
    rolling = 0
    for transfer in reversed(transfers):
        # Transfer logic
        rolling = min(max(rolling + 1 - transfer, 0), 1)

    return rolling, transfers[0]


def get_random_id(n):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

def solve_decision_support(team_id, gw, options):
    """
    Solves decision support problem for FPL

    Parameters
    ----------
    team_id: integer
        FPL ID of the team to be optimized
    gw: integer
        Upcoming (next) gameweek
    options: dict
        Options for the FPL problem
    """

    # Data
    
    data = get_data(team_id, gw-1)
    ft = get_rolling(team_id, gw-1)[0] + 1
    merged_data = data['merged_data']
    team_data = data['team_data']
    type_data = data['type_data']
    next_gw = data['next_gw']
    initial_squad = data['initial_squad']
    itb = data['itb']

    # Read options
    horizon = options.get('horizon', min(3, 38-next_gw+1))
    objective = options.get('objective', 'regular')
    decay_base = options.get('decay_base', 0.84)
    nsols = options.get('number_of_solutions', 1)
    alternative_solution = options.get('alternative_solution', '1gw-buy')
    strategy = None

    problem_name = f'ds_h{horizon}_{get_random_id(5)}'

    # Sets
    players = merged_data.index.to_list()
    element_types = type_data.index.to_list()
    teams = team_data['name'].to_list()
    gameweeks = list(range(next_gw, next_gw+horizon))
    all_gw = [next_gw-1] + gameweeks

    # Model
    model = so.Model(name=problem_name)

    # Variables
    squad = model.add_variables(players, all_gw, name='squad', vartype=so.binary)
    lineup = model.add_variables(players, gameweeks, name='lineup', vartype=so.binary)
    captain = model.add_variables(players, gameweeks, name='captain', vartype=so.binary)
    vicecap = model.add_variables(players, gameweeks, name='vicecap', vartype=so.binary)
    transfer_in = model.add_variables(players, gameweeks, name='transfer_in', vartype=so.binary)
    transfer_out = model.add_variables(players, gameweeks, name='transfer_out', vartype=so.binary)
    in_the_bank = model.add_variables(all_gw, name='itb', vartype=so.continuous, lb=0)
    free_transfers = model.add_variables(all_gw, name='ft', vartype=so.integer, lb=1, ub=2)
    penalized_transfers = model.add_variables(gameweeks, name='pt', vartype=so.integer, lb=0)
    aux = model.add_variables(gameweeks, name='aux', vartype=so.binary)
    
    # Dictionaries
    lineup_type_count = {(t,w): so.expr_sum(lineup[p,w] for p in players if merged_data.loc[p, 'element_type'] == t) for t in element_types for w in gameweeks}
    squad_type_count = {(t,w): so.expr_sum(squad[p,w] for p in players if merged_data.loc[p, 'element_type'] == t) for t in element_types for w in gameweeks}
    # player_price = (merged_data['now_cost'] / 10).to_dict()
    sell_price = (merged_data['SV']).to_dict()
    buy_price = (merged_data['BV']).to_dict()
    sold_amount = {w: so.expr_sum(sell_price[p] * transfer_out[p,w] for p in players) for w in gameweeks}
    bought_amount = {w: so.expr_sum(buy_price[p] * transfer_in[p,w] for p in players) for w in gameweeks}
    points_player_week = {(p,w): merged_data.loc[p, f'{w}_Pts']    for p in players for w in gameweeks}
    squad_count = {w: so.expr_sum(squad[p, w] for p in players) for w in gameweeks}
    number_of_transfers = {w: so.expr_sum(transfer_out[p,w] for p in players) for w in gameweeks}
    number_of_transfers[next_gw-1] = 1
    transfer_diff = {w: number_of_transfers[w] - free_transfers[w] for w in gameweeks}

    # Initial conditions
    model.add_constraints((squad[p, next_gw-1] == 1 for p in initial_squad), name='initial_squad_players')
    model.add_constraints((squad[p, next_gw-1] == 0 for p in players if p not in initial_squad), name='initial_squad_others')
    model.add_constraint(in_the_bank[next_gw-1] == itb, name='initial_itb')
    model.add_constraint(free_transfers[next_gw-1] == ft, name='initial_ft')

    # Constraints
    model.add_constraints((squad_count[w] == 15 for w in gameweeks), name='squad_count')
    model.add_constraints((so.expr_sum(lineup[p,w] for p in players) == 11 for w in gameweeks), name='lineup_count')
    model.add_constraints((so.expr_sum(captain[p,w] for p in players) == 1 for w in gameweeks), name='captain_count')
    model.add_constraints((so.expr_sum(vicecap[p,w] for p in players) == 1 for w in gameweeks), name='vicecap_count')
    model.add_constraints((lineup[p,w] <= squad[p,w] for p in players for w in gameweeks), name='lineup_squad_rel')
    model.add_constraints((captain[p,w] <= lineup[p,w] for p in players for w in gameweeks), name='captain_lineup_rel')
    model.add_constraints((vicecap[p,w] <= lineup[p,w] for p in players for w in gameweeks), name='vicecap_lineup_rel')
    model.add_constraints((captain[p,w] + vicecap[p,w] <= 1 for p in players for w in gameweeks), name='cap_vc_rel')
    model.add_constraints((lineup_type_count[t,w] == [type_data.loc[t, 'squad_min_play'], type_data.loc[t, 'squad_max_play']] for t in element_types for w in gameweeks), name='valid_formation')
    model.add_constraints((squad_type_count[t,w] == type_data.loc[t, 'squad_select'] for t in element_types for w in gameweeks), name='valid_squad')
    model.add_constraints((so.expr_sum(squad[p,w] for p in players if merged_data.loc[p, 'name'] == t) <= 3 for t in teams for w in gameweeks), name='team_limit')
    ## Transfer constraints
    model.add_constraints((squad[p,w] == squad[p,w-1] + transfer_in[p,w] - transfer_out[p,w] for p in players for w in gameweeks), name='squad_transfer_rel')
    model.add_constraints((in_the_bank[w] == in_the_bank[w-1] + sold_amount[w] - bought_amount[w] for w in gameweeks), name='cont_budget')
    ## Free transfer constraints
    model.add_constraints((free_transfers[w] == aux[w] + 1 for w in gameweeks), name='aux_ft_rel')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] <= 2 * aux[w] for w in gameweeks), name='force_aux_1')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] >= aux[w] + (-14)*(1-aux[w]) for w in gameweeks), name='force_aux_2')
    model.add_constraints((penalized_transfers[w] >= transfer_diff[w] for w in gameweeks), name='pen_transfer_rel')

    # Objectives
    gw_xp = {w: so.expr_sum(points_player_week[p,w] * (lineup[p,w] + captain[p,w] + 0.1*vicecap[p,w]) for p in players) for w in gameweeks}
    gw_total = {w: gw_xp[w] - 4 * penalized_transfers[w] for w in gameweeks}

    obj_dict = {
        'regular': -so.expr_sum(gw_total[w] for w in gameweeks),
        'decay': -so.expr_sum(gw_total[w] * pow(decay_base, w-next_gw) for w in gameweeks),
        'next_gw_regular': -gw_total[next_gw]
    }

    if isinstance(objective, list):
        strategy = options.get('multi_obj_strategy', 'weight-sum')
        if strategy == 'weight-sum':
            objw = options.get('multi_obj_weights', [0.5, 0.5])
            model.set_objective(sum(objw[i] * obj_dict[o] for (i,o) in enumerate(objective)), sense='N', name='multiple_objectives_ws')
        elif strategy == '2-step':
            model.set_objective(obj_dict[objective[0]], sense='N', name='2step_obj1')
    else:
        model.set_objective(obj_dict[objective], sense='N', name='single_objective')

    results = []

    for it in range(nsols):

        # Solve
        model.export_mps(f'tmp/{problem_name}.mps')
        command = f'cbc tmp/{problem_name}.mps solve solu tmp/{problem_name}_sol.txt'
        process = Popen(command, shell=False) # add 'stdout=DEVNULL' for disabling logs
        process.wait()

        # Parsing
        for v in model.get_variables():
            v.set_value(0)
        with open(f'tmp/{problem_name}_sol.txt', 'r') as f:
            for line in f:
                if 'objective value' in line:
                    continue
                words = line.split()
                var = model.get_variable(words[1])
                var.set_value(float(words[2]))

        if strategy == '2-step':
            obj1_val = -1 * obj_dict[objective[0]].get_value()
            obj2_val = -1 * obj_dict[objective[1]].get_value()
            print(f'Obj 1 value: {obj1_val}, Obj 2 value: {obj2_val}')
            tradeoff = options['multi_obj_tradeoff']
            obj1_lower_bound = obj1_val - tradeoff
            tradeoff_con = model.add_constraint(-1 * obj_dict[objective[0]] >= obj1_lower_bound, name='tradeoff_2s')
            model.set_objective(obj_dict[objective[1]], sense='N', name='2step_obj2')
            model.export_mps(f'tmp/{problem_name}.mps')
            command = f'cbc tmp/{problem_name}.mps mips tmp/{problem_name}_sol.txt solve solu tmp/{problem_name}_sol.txt'
            process = Popen(command, shell=False) # add 'stdout=DEVNULL' for disabling logs
            process.wait()

            for v in model.get_variables():
                v.set_value(0)
            with open(f'tmp/{problem_name}_sol.txt', 'r') as f:
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
                    is_lineup = 1 if lineup[p,w].get_value() > 0.5 else 0
                    is_vice = 1 if vicecap[p,w].get_value() > 0.5 else 0
                    is_transfer_in = 1 if transfer_in[p,w].get_value() > 0.5 else 0
                    is_transfer_out = 1 if transfer_out[p,w].get_value() > 0.5 else 0
                    position = type_data.loc[lp['element_type'], 'singular_name_short']
                    picks.append([
                        w, lp['web_name'], position, lp['element_type'], lp['name'], buy_price[p], sell_price[p], round(points_player_week[p,w],2), is_lineup, is_captain, is_vice, is_transfer_in, is_transfer_out
                    ])

        picks_df = pd.DataFrame(picks, columns=['week', 'name', 'pos', 'type', 'team', 'buy_price', 'sell_price', 'xP', 'lineup', 'captain', 'vicecaptain', 'transfer_in', 'transfer_out']).sort_values(by=['week', 'lineup', 'type', 'xP'], ascending=[True, False, True, True])
        total_xp = so.expr_sum((lineup[p,w] + captain[p,w]) * points_player_week[p,w] for p in players for w in gameweeks).get_value()
        week_xp = {w: so.expr_sum((lineup[p,w] + captain[p,w]) * points_player_week[p,w] for p in players) for w in gameweeks}


        # Writing summary
        summary_of_actions = f"\n==Solution #{it+1}==\n"
        for w in gameweeks:
            summary_of_actions += f"** GW {w}:\n"
            summary_of_actions += f"xP={round(week_xp[w].get_value(),3)}, ITB={in_the_bank[w].get_value()}, FT={free_transfers[w].get_value()}, PT={penalized_transfers[w].get_value()}\n"
            for p in players:
                if transfer_in[p,w].get_value() > 0.5:
                    summary_of_actions += f"Buy {p} - {merged_data['web_name'][p]}\n"
                if transfer_out[p,w].get_value() > 0.5:
                    summary_of_actions += f"Sell {p} - {merged_data['web_name'][p]}\n"
        print(summary_of_actions)

        next_gw_action = "Buy: "
        bought = []
        for p in players:
            if transfer_in[p, next_gw].get_value() > 0.5:
                bought.append(merged_data['web_name'][p])
        next_gw_action += ', '.join(bought)
        sold = []
        for p in players:
            if transfer_out[p, next_gw].get_value() > 0.5:
                sold.append(merged_data['web_name'][p])
        next_gw_action += " Sell: " + ', '.join(sold)    

        results.append({
            'iter': it+1,
            'picks': picks_df,
            'objective': -round(model.get_objective_value(),3),
            'next_gw_obj': round(gw_total[next_gw].get_value(),3),
            'summary': summary_of_actions,
            'total_xp': total_xp,
            'next_gw_xp': week_xp[next_gw].get_value(),
            'next_gw_action': next_gw_action
        })

        if it != nsols-1:
            if alternative_solution == '1gw-buy':
                actions = so.expr_sum(transfer_in[p, next_gw] for p in players if transfer_in[p, next_gw].get_value() > 0.5)
                gw_range = [next_gw]
            elif alternative_solution == 'horizon-buy':
                actions = so.expr_sum(transfer_in[p, w] for p in players for w in gameweeks if transfer_in[p, w].get_value() > 0.5)
                gw_range = gameweeks
            elif alternative_solution == '1gw-buy-sell':
                actions = so.expr_sum(transfer_in[p, next_gw] for p in players if transfer_in[p, next_gw].get_value() > 0.5) +\
                          so.expr_sum(transfer_out[p, next_gw] for p in players if transfer_out[p, next_gw].get_value() > 0.5)
                gw_range = [next_gw]
            elif alternative_solution == 'horizon-buy-sell':
                actions = so.expr_sum(transfer_in[p, w] for p in players for w in gameweeks if transfer_in[p, w].get_value() > 0.5) +\
                          so.expr_sum(transfer_out[p, w] for p in players for w in gameweeks if transfer_out[p, w].get_value() > 0.5)
                gw_range = gameweeks

            if actions.get_value() != 0:
                model.add_constraint(actions <= actions.get_value() - 1, name=f'cutoff_{it}')
            else:
                model.add_constraint(so.expr_sum(number_of_transfers[w] for w in gw_range) >= 1, name=f'cutoff_{it}')

        if strategy == '2-step':
            model.drop_constraint(tradeoff_con)

        try:
            pathlib.Path(f'tmp/{problem_name}.mps').unlink()
            pathlib.Path(f'tmp/{problem_name}_sol.txt').unlink()
        except:
            pass

    return {'model': model, 'results': results}

if __name__ == '__main__':

    # Generating Alternative Solutions

    r = solve_decision_support(team_id=159049, gw=35, 
        options={
            'number_of_solutions': 10,
            'horizon':4,
            'objective':'regular', # you can use 'regular' or 'decay'
            'alternative_solution': '1gw-buy'} # you can use '1gw-buy', '1gw-buy-sell', 'horizon-buy', 'horizon-buy-sell'
        )
    res = r['results']
    for i in res:
        i['picks'].to_csv(f"../output/solution{i['iter']}.csv")
    res_df = pd.DataFrame([
        (i['iter'],
        i['objective'],
        i['next_gw_obj'],
        i['total_xp'],
        i['next_gw_xp'],
        i['next_gw_action']) for i in res
    ] , columns=['iteration', 'objective', 'next_gw_obj', 'total_xp', 'next_gw_xp', 'next_gw_action']).set_index('iteration')
    print(res_df)
    res_df.to_csv("../output/ds_alternative_summary.csv")
    p = res_df.plot.scatter(x='objective', y='next_gw_obj', c='Blue', title='Total xP vs Next GW xP')
    p.get_figure().savefig('../output/ds_alternative.png')


    # Solving Multiobjective Optimization (Weight-sum method)

    # r = solve_decision_support(team_id=216079, gw=35, 
    #     options={
    #         'number_of_solutions': 5,
    #         'horizon':3,
    #         'objective': ['regular', 'next_gw_regular'],
    #         'multi_obj_weights': [0.5/150, 0.5/50],
    #         'alternative_solution': '1gw-buy'}
    #     )
    # res = r['results']
    # for i in res:
    #     i['picks'].to_csv(f"../output/multiobj_ws_solution{i['iter']}.csv")
    # res_df = pd.DataFrame([
    #     (i['iter'],
    #     i['objective'],
    #     i['next_gw_obj'],
    #     i['total_xp'],
    #     i['next_gw_xp'],
    #     i['next_gw_action']) for i in res
    # ] , columns=['iteration', 'objective', 'next_gw_obj', 'total_xp', 'next_gw_xp', 'next_gw_action']).set_index('iteration')
    # print(res_df)
    # res_df.to_csv("../output/ds_ws_summary.csv")
    # p = res_df.plot.scatter(x='objective', y='next_gw_obj', c='Blue', title='Total xP vs Next GW xP')
    # p.get_figure().savefig('../output/ds_ws.png')

    
    # Weight-sum in a loop

    # options={
    #     'number_of_solutions': 3,
    #     'horizon': 3,
    #     'objective': ['regular', 'next_gw_regular'],
    #     'multi_obj_strategy': 'weight-sum',
    #     'multi_obj_weights': [0.5/150, 0.5/50],
    #     'alternative_solution': '1gw-buy'}

    # options_list = []
    # for s in range(0, 11, 2):
    #     opt_clone = dict(options)
    #     opt_clone['multi_obj_weights'] = [(s/10)/150, (1-s/10)/50]
    #     options_list.append(opt_clone)
    # with ProcessPoolExecutor(max_workers=16) as executor:
    #     responses = list(executor.map(
    #         solve_decision_support, 
    #         itertools.repeat(216079),
    #         itertools.repeat(35),
    #         options_list
    #         ))
    # all_responses = []
    # for (k, response) in enumerate(responses):
    #     all_responses.append(
    #         pd.DataFrame([
    #             (k,
    #             i['iter'],
    #             i['objective'],
    #             i['next_gw_obj'],
    #             i['total_xp'],
    #             i['next_gw_xp'],
    #             i['next_gw_action']) for i in response['results']
    #         ] , columns=['group', 'iteration', 'objective', 'next_gw_obj', 'total_xp', 'next_gw_xp', 'next_gw_action'])
    #     )
    #     for p in response['results']:
    #         p['picks'].to_csv(f"../output/multiobj_ws_solution_group{k}_{p['iter']}.csv")

    # all_responses_df = pd.concat(all_responses)
    # print(all_responses_df)
    # all_responses_df.to_csv("../output/ds_ws_group_summary.csv")
    # p = all_responses_df.plot.scatter(x='objective', y='next_gw_obj', c='Blue', title='Total xP vs Next GW xP')
    # p.get_figure().savefig('../output/ds_ws_group.png')



    # Solving Multiobjective Optimization (2-Step Method)

    # options={
    #     'number_of_solutions': 1,
    #     'horizon': 3,
    #     'objective': ['regular', 'next_gw_regular'],
    #     'multi_obj_strategy': '2-step',
    #     'multi_obj_tradeoff': 2,
    #     'alternative_solution': '1gw-buy'}

    # r = solve_decision_support(team_id=216079, gw=35, options=options)
    # res = r['results']
    # for i in res:
    #     i['picks'].to_csv(f"../output/multiobj_2step_solution{i['iter']}.csv")
    # res_df = pd.DataFrame([
    #     (i['iter'],
    #     i['objective'],
    #     i['next_gw_obj'],
    #     i['total_xp'],
    #     i['next_gw_xp'],
    #     i['next_gw_action']) for i in res
    # ] , columns=['iteration', 'objective', 'next_gw_obj', 'total_xp', 'next_gw_xp', 'next_gw_action']).set_index('iteration')
    # print(res_df)
    # res_df.to_csv("../output/ds_2step_summary.csv")
    # p = res_df.plot.scatter(x='objective', y='next_gw_obj', c='Blue', title='Total xP vs Next GW xP')
    # p.get_figure().savefig('../output/ds_2step.png')
