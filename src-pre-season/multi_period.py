import pandas as pd
import sasoptpy as so
import requests
from subprocess import Popen, DEVNULL

# Solves the pre-season optimization problem

def get_data():
    r = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
    fpl_data = r.json()
    element_data = pd.DataFrame(fpl_data['elements'])
    team_data = pd.DataFrame(fpl_data['teams'])
    elements_team = pd.merge(element_data, team_data, left_on='team', right_on='id')
    review_data = pd.read_csv('../data/fplreview.csv')
    review_data = review_data.fillna(0)
    merged_data = pd.merge(elements_team, review_data, left_on=['name', 'web_name'], right_on=['Team', 'Name'])
    merged_data.set_index(['id_x'], inplace=True)
    next_gw = int(review_data.keys()[5].split('_')[0])
    type_data = pd.DataFrame(fpl_data['element_types']).set_index(['id'])

    initial_squad = []
    itb = 100

    return {'merged_data': merged_data, 'team_data': team_data, 'type_data': type_data, 'next_gw': next_gw, 'initial_squad': initial_squad, 'itb': itb}

def solve_multi_period_pre_season_fpl(horizon, objective='regular', decay_base=0.84, no_transfer=False):
    """
    Solves multi-objective FPL problem with transfers

    Parameters
    ----------
    team_id: integer
        FPL ID of the team to be optimized
    horizon: integer
        Number of weeks to consider in optimization
    objective: string
        Type of objective "regular" or "decay"
    decay_base: float
        Base for the decay function
    """

    # Data
    problem_name = f'mp_h{horizon}_regular' if objective == 'regular' else f'mp_h{horizon}_o{objective[0]}_d{decay_base}'
    data = get_data()
    merged_data = data['merged_data']
    merged_data.drop_duplicates(inplace=True, keep='first') # Fix for duplicate lines
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
    free_transfers = model.add_variables(gameweeks, name='ft', vartype=so.integer, lb=1, ub=2)
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
    model.add_constraint(in_the_bank[next_gw-1] == itb, name='initial_itb')
    model.add_constraints((squad[p, next_gw-1] == 0 for p in players), name='initial_squad')
    model.add_constraint(free_transfers[next_gw] == 1, name='initial_ft_1')
    model.add_constraint(free_transfers[next_gw+1] == 1, name='initial_ft_2')

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
    model.add_constraints((free_transfers[w] == aux[w] + 1 for w in gameweeks if w > 2), name='aux_ft_rel')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] <= 2 * aux[w] for w in gameweeks if w > 2), name='force_aux_1')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] >= aux[w] + (-14)*(1-aux[w]) for w in gameweeks if w > 2), name='force_aux_2')
    model.add_constraints((penalized_transfers[w] >= transfer_diff[w] for w in gameweeks), name='pen_transfer_rel')

    model.add_constraints((transfer_in[p,w] + transfer_out[p,w] <= 1 for p in players for w in gameweeks), name='no_buy_sell')
    # Custom constraint
    if no_transfer:
        model.add_constraint(so.expr_sum(transfer_out[p,w] for p in players for w in gameweeks) == 0, name='no_transfer')

    # Objectives
    gw_xp = {w: so.expr_sum(points_player_week[p,w] * (lineup[p,w] + captain[p,w] + 0.1*vicecap[p,w]) for p in players) for w in gameweeks}
    gw_total = {w: gw_xp[w] - 4 * penalized_transfers[w] for w in gameweeks}
    if objective == 'regular':
        total_xp = so.expr_sum(gw_total[w] for w in gameweeks)
        model.set_objective(-total_xp, sense='N', name='total_regular_xp')
    else:
        decay_objective = so.expr_sum(gw_total[w] * pow(decay_base, w-next_gw) for w in gameweeks)
        model.set_objective(-decay_objective, sense='N', name='total_decay_xp')

    # Solve
    model.export_mps(f'{problem_name}.mps')
    command = f'cbc {problem_name}.mps solve solu {problem_name}_sol.txt'
    process = Popen(command, shell=False) # add 'stdout=DEVNULL' for disabling logs
    process.wait()

    # Parsing
    with open(f'{problem_name}_sol.txt', 'r') as f:
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
                is_squad = 1 if squad[p,w].get_value() > 0.5 else 0
                is_captain = 1 if captain[p,w].get_value() > 0.5 else 0
                is_lineup = 1 if lineup[p,w].get_value() > 0.5 else 0
                is_vice = 1 if vicecap[p,w].get_value() > 0.5 else 0
                is_transfer_in = 1 if transfer_in[p,w].get_value() > 0.5 else 0
                is_transfer_out = 1 if transfer_out[p,w].get_value() > 0.5 else 0
                position = type_data.loc[lp['element_type'], 'singular_name_short']
                picks.append([
                    w, lp['web_name'], position, lp['element_type'], lp['name'], buy_price[p], sell_price[p], round(points_player_week[p,w],2), is_squad, is_lineup, is_captain, is_vice, is_transfer_in, is_transfer_out
                ])

    picks_df = pd.DataFrame(picks, columns=['week', 'name', 'pos', 'type', 'team', 'buy_price', 'sell_price', 'xP', 'squad', 'lineup', 'captain', 'vicecaptain', 'transfer_in', 'transfer_out']).sort_values(by=['week', 'lineup', 'type', 'xP'], ascending=[True, False, True, True])
    total_xp = so.expr_sum((lineup[p,w] + captain[p,w]) * points_player_week[p,w] for p in players for w in gameweeks).get_value()

    # Writing summary
    summary_of_actions = ""
    for w in gameweeks:
        summary_of_actions += f"** GW {w}:\n"
        summary_of_actions += f"ITB = {in_the_bank[w].get_value()}, FT={free_transfers[w].get_value()}, PT={penalized_transfers[w].get_value()}\n"
        for p in players:
            if transfer_in[p,w].get_value() > 0.5:
                summary_of_actions += f"Buy {p} - {merged_data['web_name'][p]}\n"
            if transfer_out[p,w].get_value() > 0.5:
                summary_of_actions += f"Sell {p} - {merged_data['web_name'][p]}\n"

    return {'model': model, 'picks': picks_df, 'total_xp': total_xp, 'summary': summary_of_actions}

if __name__ == '__main__':

    r = solve_multi_period_pre_season_fpl(horizon=4, objective='regular')
    print(r['picks'])
    print(r['summary'])
    r['picks'].to_csv('optimal_plan_regular.csv')

    r = solve_multi_period_pre_season_fpl(horizon=4, objective='decay', decay_base=0.84)
    print(r['picks'])
    print(r['summary'])
    r['picks'].to_csv('optimal_plan_decay.csv')

    r = solve_multi_period_pre_season_fpl(horizon=4, objective='decay', decay_base=0.84, no_transfer=True)
    print(r['picks'])
    print(r['summary'])
    r['picks'].to_csv('optimal_plan_decay_no_transfer.csv')
