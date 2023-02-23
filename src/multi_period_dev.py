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
from data_parser import read_data

def get_random_id(n):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def xmin_to_prob(xmin, sub_on=0.5, sub_off=0.3):
    start = min( max ( (xmin - 25 * sub_on) / (90 * (1-sub_off) + 65 * sub_off - 25 * sub_on), 0.001), 0.999)
    return start + (1-start) * sub_on

def connect():
    print("This method is provided for people who want to automate login. However with 2FA changes, it is unlikely to work, and I'd suggest using team.json method from now on as explained in README file.")
    base_folder = Path()
    with open(base_folder / "../data/login.json") as f:
        credentials = json.load(f)
    session = Session()
    payload = {
        'password': credentials['password'],
        'login': credentials['email'],
        'redirect_uri': 'https://fantasy.premierleague.com/',
        'app': 'plfpl-web'
    }
    headers = {
        "user-agent": "Dalvik/2.1.0 (Linux; U; Android 6.0; Android SDK built for x86_64 Build/MASTER)",
        "cookie": "pl_euconsent-v2=CPUn1YtPUn1YtFCABAENBRCsAP_AAH_AAAwIF5wAQF5gXnABAXmAAAAA.YAAAAAAAAAAA; pl_euconsent-v2-intent-confirmed=^{^%^22tcf^%^22:^[755^]^%^2C^%^22oob^%^22:^[^]^}; pl_oob-vendors=^{^}; datadome=q_f99WYn0dSxMnuNGw8TQuIf2YeVio7m7Yk-jVBaWf43sM2v86YYVH17srelKLrR6B9ynB5V2z7pNs~jG6VKc~4u3up4WBrCYD6rekwuM3cRG8.9XbLGXAE4Cz~BWyv"
    }
    t = session.get('https://fantasy.premierleague.com/')
    time.sleep(1)
    v = session.post('https://users.premierleague.com/accounts/login/', data=payload, headers=headers, cookies=session.cookies)
    if v.status_code != 200:
        print("Login attempt failed, checking local file")
        if os.path.exists('team.json'):
            return [session, None]
        print("""If you are getting this error, do the following: 
            - Open your browser and log in to FPL
            - After the login, go to following link (replace 'TEAM_ID' with your team ID)
              > https://fantasy.premierleague.com/api/my-team/TEAM_ID/
            - Create a file in this directory called 'team.json' and paste the content.
        """)
        return [None, None]
    else:
        r = session.get('https://fantasy.premierleague.com/api/me/')
        if r.status_code != 200:
            raise ValueError('Cannot read data')
        try:
            return [session, r.json()['player']['entry']]
        except:
            return [None, None]
    


def get_my_data(session, team_id):
    r = session.get(f"https://fantasy.premierleague.com/api/my-team/{team_id}/")
    d = r.json()
    d['team_id'] = team_id
    return d


def generate_team_json(team_id, options):
    BASE_URL = "https://fantasy.premierleague.com/api"
    with requests.Session() as session:
        static_url = f"{BASE_URL}/bootstrap-static/"
        static = session.get(static_url).json()
        next_gw = [x for x in static["events"] if x["is_next"]][0]["id"]

        start_prices = {x["id"]: x["now_cost"] - x["cost_change_start"] for x in static["elements"]}
        gw1_url = f"{BASE_URL}/entry/{team_id}/event/1/picks/"
        gw1 = session.get(gw1_url).json()

        transfers_url = f"{BASE_URL}/entry/{team_id}/transfers/"
        transfers = session.get(transfers_url).json()[::-1]

    # squad will remain an ID:puchase_price map throughout iteration over transfers
    # once they have been iterated through, can then add on the current selling price
    squad = {x["element"]: start_prices[x["element"]] for x in gw1["picks"]}

    itb = 1000 - sum(squad.values())
    for t in transfers:
        itb += t["element_out_cost"]
        itb -= t["element_in_cost"]
        del squad[t["element_out"]]
        squad[t["element_in"]] = t["element_in_cost"]

    fts = calculate_fts(transfers, next_gw)
    my_data = {
        "chips": [],
        "picks": [],
        "team_id": team_id,
        "transfers": {
            "bank": itb,
            "limit": fts,
            "made": 0,
        }
    }
    for player_id, purchase_price in squad.items():
        now_cost = [x for x in static["elements"] if x["id"] == player_id][0]["now_cost"]

        diff = now_cost - purchase_price
        if diff > 0:
            selling_price = purchase_price + diff // 2
        else:
            selling_price = now_cost

        my_data["picks"].append(
            {
                "element": player_id,
                "purchase_price": purchase_price,
                "selling_price": selling_price,
            }
        )

    # handle transfers that have already been made this gameweek
    current_gw_transfers = options.get("current_gw_transfers", [])
    for transfer in current_gw_transfers:
        player_in = transfer.get("element_in", None)
        purchase_price = transfer.get("element_in_cost", None)
        player_out = transfer.get("element_out", None)
        selling_price = transfer.get("element_out_cost", None)

        if not all([player_in, purchase_price, player_out, selling_price]):
            print(f"""Not a valid transfer: 'element_in', 'element_in_cost', 'element_out', and 'element_out_cost'
                        must all be provided \n {json.dumps(transfer, indent=2)}""")
            exit(0)

        my_data["transfers"]["bank"] -= purchase_price
        my_data["transfers"]["bank"] += selling_price
        my_data["transfers"]["made"] += 1

        # calculate current price of new player to check if they have risen >= 2 times since making transfer
        current_price = [x for x in static["elements"] if x["id"] == player_in][0]["now_cost"]
        diff = current_price - purchase_price
        if diff > 0:
            selling_price = purchase_price + diff // 2
        else:
            selling_price = current_price

        my_data["picks"] = [x for x in my_data["picks"] if x["element"] != player_out]
        my_data["picks"].append(
            {
                "element": player_in,
                "purchase_price": purchase_price,
                "selling_price": selling_price
            }
        )
    return my_data


def calculate_fts(transfers, next_gw):
    n_transfers = {gw: 0 for gw in range(2, next_gw)}
    for t in transfers:
        n_transfers[t["event"]] += 1
    fts = {gw: 0 for gw in range(2, next_gw + 1)}
    fts[2] = 1
    for i in range(3, next_gw + 1):
        fts[i] = fts[i - 1]
        fts[i] -= n_transfers[i - 1]
        fts[i] = max(fts[i], 0)
        fts[i] += 1
        fts[i] = min(fts[i], 2)
    return fts[next_gw]


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

    datasource = options.get('datasource', 'review')
    data_weights = options.get('data_weights', {'review': 100})

    data = read_data(options, datasource, data_weights)
    
    data = data.fillna(0)
    if 'ID' in data:
        data['review_id'] = data['ID']
    else:
        data['review_id'] = data.index+1
    
    if options.get('export_data', '') != '' and datasource == 'mixed':
        data.to_csv(f"../data/{options['export_data']}")

    merged_data = pd.merge(elements_team, data, left_on='id_x', right_on='review_id')
    merged_data.set_index(['id_x'], inplace=True)

    # Check if data exists
    for week in range(gw, min(39, gw+horizon)):
        if f'{week}_Pts' not in data.keys():
            raise ValueError(f"{week}_Pts is not inside prediction data, change your horizon parameter or update your prediction data")

    original_keys = merged_data.columns.to_list()
    keys = [k for k in original_keys if "_Pts" in k]
    min_keys = [k for k in original_keys if "_xMins" in k]
    merged_data['total_ev'] = merged_data[keys].sum(axis=1)
    merged_data['total_min'] = merged_data[min_keys].sum(axis=1)

    merged_data.sort_values(by=['total_ev'], ascending=[False], inplace=True)

    # Filter players by xMin
    initial_squad = [int(i['element']) for i in my_data['picks']]
    xmin_lb = options.get('xmin_lb', 1)
    print(len(merged_data), "total players (before)")
    merged_data = merged_data[(merged_data['total_min'] >= xmin_lb) | (merged_data['review_id'].isin(initial_squad))].copy()

    # Filter by ev per price
    ev_per_price_cutoff = options.get('ev_per_price_cutoff', 0)
    safe_players = initial_squad + options.get('locked', []) + options.get('banned', []) + options.get('keep', [])
    if ev_per_price_cutoff != 0:
        cutoff = (merged_data['total_ev'] / merged_data['now_cost']).quantile(ev_per_price_cutoff/100)
        merged_data = merged_data[(merged_data['total_ev'] / merged_data['now_cost'] > cutoff) | (merged_data['review_id'].isin(safe_players))].copy()

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
    
    preseason = options.get('preseason', False)
    if not preseason:
        for i in my_data['picks']:
            if buy_price[i['element']] != sell_price[i['element']]:
                price_modified_players.append(i['element'])
                print(f"Added player {i['element']} to list, buy price {buy_price[i['element']]} sell price {sell_price[i['element']]}")

    itb = my_data['transfers']['bank']/10
    if my_data['transfers']['limit'] is None:
        ft = 1
    else:
        ft = my_data['transfers']['limit'] - my_data['transfers']['made']
    if ft < 0:
        ft = 0
    # If wildcard is active, then you have: "status_for_entry": "active" under my_data['chips']
    for c in my_data['chips']:
        if c['name'] == 'wildcard' and c['status_for_entry'] == 'active':
            ft = 1
            options['use_wc'] = gw
            if options['chip_limits']['wc'] == 0:
                options['chip_limits']['wc'] = 1
            break

    # Fixture info
    team_code_dict = team_data.set_index('id')['name'].to_dict()
    fixture_data = requests.get('https://fantasy.premierleague.com/api/fixtures/').json()
    fixtures = [{'gw': f['event'], 'home': team_code_dict[f['team_h']], 'away': team_code_dict[f['team_a']]} for f in fixture_data]

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
        'ft': ft,
        'fixtures': fixtures
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
    objective = options.get('objective', 'decay')
    decay_base = options.get('decay_base', 0.84)
    bench_weights = options.get('bench_weights', {0: 0.03, 1: 0.21, 2: 0.06, 3: 0.002})
    bench_weights = {int(key): value for (key,value) in bench_weights.items()}
    # wc_limit = options.get('wc_limit', 0)
    ft_value = options.get('ft_value', 1.5)
    itb_value = options.get('itb_value', 0.08)
    ft = data.get('ft', 1)
    if ft <= 0:
        ft = 0
    chip_limits = options.get('chip_limits', dict())
    current_gw_transfers = options.get("current_gw_transfers", [])
    booked_transfers = options.get('booked_transfers', [])
    preseason = options.get('preseason', False)

    # Data
    problem_name = f'mp_h{horizon}_regular' if objective == 'regular' else f'mp_h{horizon}_o{objective[0]}_d{decay_base}'
    merged_data = data['merged_data']
    team_data = data['team_data']
    type_data = data['type_data']
    next_gw = data['next_gw']
    initial_squad = data['initial_squad']
    itb = data['itb']
    fixtures = data['fixtures']
    if preseason:
        itb = 100
        threshold_gw = 2
    else:
        threshold_gw = next_gw

    # Sets
    players = merged_data.index.to_list()
    element_types = type_data.index.to_list()
    teams = team_data['name'].to_list()
    last_gw = next_gw + horizon - 1
    gameweeks = list(range(next_gw, last_gw + 1))
    all_gw = [next_gw-1] + gameweeks
    order = [0, 1, 2, 3]
    price_modified_players = data['price_modified_players']

    # Model
    model = so.Model(name=problem_name)

    # Variables
    squad = model.add_variables(players, all_gw, name='squad', vartype=so.binary)
    squad_fh = model.add_variables(players, gameweeks, name='squad_fh', vartype=so.binary)
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
    use_bb = model.add_variables(gameweeks, name='use_bb', vartype=so.binary)
    use_fh = model.add_variables(gameweeks, name='use_fh', vartype=so.binary)

    # Dictionaries
    lineup_type_count = {(t,w): so.expr_sum(lineup[p,w] for p in players if merged_data.loc[p, 'element_type'] == t) for t in element_types for w in gameweeks}
    squad_type_count = {(t,w): so.expr_sum(squad[p,w] for p in players if merged_data.loc[p, 'element_type'] == t) for t in element_types for w in gameweeks}
    squad_fh_type_count = {(t,w): so.expr_sum(squad_fh[p,w] for p in players if merged_data.loc[p, 'element_type'] == t) for t in element_types for w in gameweeks}
    player_type = merged_data['element_type'].to_dict()
    # player_price = (merged_data['now_cost'] / 10).to_dict()
    sell_price = data['sell_price']
    buy_price = data['buy_price']
    sold_amount = {w: 
        so.expr_sum(sell_price[p] * transfer_out_first[p,w] for p in price_modified_players) +\
        so.expr_sum(buy_price[p] * transfer_out_regular[p,w] for p in players)
        for w in gameweeks}
    fh_sell_price = {p: sell_price[p] if p in price_modified_players else buy_price[p] for p in players}
    bought_amount = {w: so.expr_sum(buy_price[p] * transfer_in[p,w] for p in players) for w in gameweeks}
    points_player_week = {(p,w): merged_data.loc[p, f'{w}_Pts'] for p in players for w in gameweeks}
    minutes_player_week = {(p,w): merged_data.loc[p, f'{w}_xMins'] for p in players for w in gameweeks}
    squad_count = {w: so.expr_sum(squad[p, w] for p in players) for w in gameweeks}
    squad_fh_count = {w: so.expr_sum(squad_fh[p, w] for p in players) for w in gameweeks}
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
    model.add_constraints((squad_fh_count[w] == 15 * use_fh[w] for w in gameweeks), name='squad_fh_count')
    model.add_constraints((so.expr_sum(lineup[p,w] for p in players) == 11 + 4 * use_bb[w] for w in gameweeks), name='lineup_count')
    model.add_constraints((so.expr_sum(bench[p,w,0] for p in players if player_type[p] == 1) == 1 - use_bb[w] for w in gameweeks), name='bench_gk')
    model.add_constraints((so.expr_sum(bench[p,w,o] for p in players) == 1 - use_bb[w] for w in gameweeks for o in [1,2,3]), name='bench_count')
    model.add_constraints((so.expr_sum(captain[p,w] for p in players) == 1 for w in gameweeks), name='captain_count')
    model.add_constraints((so.expr_sum(vicecap[p,w] for p in players) == 1 for w in gameweeks), name='vicecap_count')
    model.add_constraints((lineup[p,w] <= squad[p,w] + use_fh[w] for p in players for w in gameweeks), name='lineup_squad_rel')
    model.add_constraints((bench[p,w,o] <= squad[p,w] + use_fh[w] for p in players for w in gameweeks for o in order), name='bench_squad_rel')
    model.add_constraints((lineup[p,w] <= squad_fh[p,w] + 1 - use_fh[w] for p in players for w in gameweeks), name='lineup_squad_fh_rel')
    model.add_constraints((bench[p,w,o] <= squad_fh[p,w] + 1 - use_fh[w] for p in players for w in gameweeks for o in order), name='bench_squad_fh_rel')
    model.add_constraints((captain[p,w] <= lineup[p,w] for p in players for w in gameweeks), name='captain_lineup_rel')
    model.add_constraints((vicecap[p,w] <= lineup[p,w] for p in players for w in gameweeks), name='vicecap_lineup_rel')
    model.add_constraints((captain[p,w] + vicecap[p,w] <= 1 for p in players for w in gameweeks), name='cap_vc_rel')
    model.add_constraints((lineup[p,w] + so.expr_sum(bench[p,w,o] for o in order) <= 1 for p in players for w in gameweeks), name='lineup_bench_rel')
    model.add_constraints((lineup_type_count[t,w] >= type_data.loc[t, 'squad_min_play'] for t in element_types for w in gameweeks), name='valid_formation_lb')
    model.add_constraints((lineup_type_count[t,w] <= type_data.loc[t, 'squad_max_play'] + use_bb[w] for t in element_types for w in gameweeks), name='valid_formation_ub')
    model.add_constraints((squad_type_count[t,w] == type_data.loc[t, 'squad_select'] for t in element_types for w in gameweeks), name='valid_squad')
    model.add_constraints((squad_fh_type_count[t,w] == type_data.loc[t, 'squad_select'] * use_fh[w] for t in element_types for w in gameweeks), name='valid_squad_fh')
    model.add_constraints((so.expr_sum(squad[p,w] for p in players if merged_data.loc[p, 'name'] == t) <= 3 for t in teams for w in gameweeks), name='team_limit')
    model.add_constraints((so.expr_sum(squad_fh[p,w] for p in players if merged_data.loc[p, 'name'] == t) <= 3 * use_fh[w] for t in teams for w in gameweeks), name='team_limit_fh')
    ## Transfer constraints
    model.add_constraints((squad[p,w] == squad[p,w-1] + transfer_in[p,w] - transfer_out[p,w] for p in players for w in gameweeks), name='squad_transfer_rel')
    model.add_constraints((in_the_bank[w] == in_the_bank[w-1] + sold_amount[w] - bought_amount[w] for w in gameweeks), name='cont_budget')
    model.add_constraints((so.expr_sum(fh_sell_price[p] * squad[p,w-1] for p in players) + in_the_bank[w-1] >= so.expr_sum(fh_sell_price[p] * squad_fh[p,w] for p in players) for w in gameweeks), name='fh_budget')
    model.add_constraints((transfer_in[p,w] <= 1-use_fh[w] for p in players for w in gameweeks), name='no_tr_in_fh')
    model.add_constraints((transfer_out[p,w] <= 1-use_fh[w] for p in players for w in gameweeks), name='no_tr_out_fh')
    ## Free transfer constraints
    model.add_constraints((free_transfers[w] == aux[w] + 1 for w in gameweeks if w > threshold_gw), name='aux_ft_rel')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] - 2 * use_wc[w-1] - 2 * use_fh[w-1] <= 2 * aux[w] for w in gameweeks if w > threshold_gw), name='force_aux_1')
    model.add_constraints((free_transfers[w-1] - number_of_transfers[w-1] - 2 * use_wc[w-1] - 2 * use_fh[w-1] >= aux[w] + (-14)*(1-aux[w]) for w in gameweeks if w > threshold_gw), name='force_aux_2')
    if preseason and threshold_gw in gameweeks:
        model.add_constraint(free_transfers[threshold_gw] == 1, name='ps_initial_ft')
    model.add_constraints((penalized_transfers[w] >= transfer_diff[w] for w in gameweeks), name='pen_transfer_rel')
    ## Chip constraints
    model.add_constraints((use_wc[w] + use_fh[w] + use_bb[w] <= 1 for w in gameweeks), name='single_chip')
    model.add_constraints((aux[w] <= 1-use_wc[w-1] for w in gameweeks if w > next_gw), name='ft_after_wc')
    model.add_constraints((aux[w] <= 1-use_fh[w-1] for w in gameweeks if w > next_gw), name='ft_after_fh')

    model.add_constraint(so.expr_sum(use_wc[w] for w in gameweeks) <= chip_limits.get('wc', 0), name='use_wc_limit')
    model.add_constraint(so.expr_sum(use_bb[w] for w in gameweeks) <= chip_limits.get('bb', 0), name='use_bb_limit')
    model.add_constraint(so.expr_sum(use_fh[w] for w in gameweeks) <= chip_limits.get('fh', 0), name='use_fh_limit')
    model.add_constraints((squad_fh[p,w] <= use_fh[w] for p in players for w in gameweeks), name='fh_squad_logic')

    if options.get('use_wc', None) is not None:
        model.add_constraint(use_wc[options['use_wc']] == 1, name='force_wc')
    if options.get('use_bb', None) is not None:
        model.add_constraint(use_bb[options['use_bb']] == 1, name='force_bb')
    if options.get('use_fh', None) is not None:
        model.add_constraint(use_fh[options['use_fh']] == 1, name='force_fh')
    
    ## Multiple-sell fix
    model.add_constraints((transfer_out_first[p,w] + transfer_out_regular[p,w] <= 1 for p in price_modified_players for w in gameweeks), name='multi_sell_1')
    model.add_constraints((
        horizon * so.expr_sum(transfer_out_first[p,w] for w in gameweeks if w <= wbar) >=
        so.expr_sum(transfer_out_regular[p,w] for w in gameweeks if w >= wbar)
        for p in price_modified_players for wbar in gameweeks
    ), name='multi_sell_2')
    model.add_constraints((so.expr_sum(transfer_out_first[p,w] for w in gameweeks) <= 1 for p in price_modified_players), name='multi_sell_3')

    ## Transfer in/out fix
    model.add_constraints((transfer_in[p,w] + transfer_out[p,w] <= 1 for p in players for w in gameweeks), name='tr_in_out_limit')

    ## Optional constraints
    if options.get('banned', None) is not None:
        banned_players = options['banned']
        model.add_constraints((so.expr_sum(squad[p,w] for w in gameweeks) == 0 for p in banned_players), name='ban_player')

    if options.get('locked', None) is not None:
        locked_players = options['locked']
        model.add_constraints((squad[p,w] == 1 for p in locked_players for w in gameweeks), name='lock_player')

    if options.get("no_future_transfer"):
        model.add_constraint(so.expr_sum(transfer_in[p,w] for p in players for w in gameweeks if w > next_gw and w != options.get('use_wc')) == 0, name='no_future_transfer')

    if options.get("no_transfer_last_gws"):
        no_tr_gws = options['no_transfer_last_gws']
        if horizon > no_tr_gws:
            model.add_constraints((so.expr_sum(transfer_in[p,w] for p in players) <= 15 * use_wc[w] for w in gameweeks if w > last_gw - no_tr_gws), name='tr_ban_gws')

    if options.get("num_transfers", None) is not None:
        model.add_constraint(so.expr_sum(transfer_in[p,next_gw] for p in players) == options['num_transfers'], name='tr_limit')

    if options.get("hit_limit", None) is not None:
        model.add_constraint(so.expr_sum(penalized_transfers[w] for w in gameweeks) <= options['hit_limit'], name='horizon_hit_limit')

    if options.get("future_transfer_limit", None) is not None:
        model.add_constraint(so.expr_sum(transfer_in[p,w] for p in players for w in gameweeks if w > next_gw and w != options.get('use_wc')) <= options['future_transfer_limit'], name='future_tr_limit')

    if options.get("no_transfer_gws", None) is not None:
        if len(options['no_transfer_gws']) > 0:
            model.add_constraint(so.expr_sum(transfer_in[p,w] for p in players for w in options['no_transfer_gws']) == 0, name='banned_gws_for_tr')
    
    for booked_transfer in booked_transfers:
        transfer_gw = booked_transfer.get('gw', None)

        if transfer_gw is None:
            continue

        player_in = booked_transfer.get('transfer_in', None)
        player_out = booked_transfer.get('transfer_out', None)

        if player_in is not None:
            model.add_constraint(transfer_in[player_in, transfer_gw] == 1,
                                 name=f'booked_transfer_in_{transfer_gw}_{player_in}')
        if player_out is not None:
            model.add_constraint(transfer_out[player_out, transfer_gw] == 1,
                                 name=f'booked_transfer_out_{transfer_gw}_{player_out}')

    if options.get('no_opposing_play') is True:
        for gw in gameweeks:
            gw_games = [i for i in fixtures if i['gw'] == gw]
            opposing_players = [(p1,p2) for f in gw_games for p1 in players if merged_data.loc[p1, 'name'] == f['home'] for p2 in players if merged_data.loc[p2, 'name'] == f['away']]
            model.add_constraints((lineup[p1,gw] + lineup[p2,gw] <= 1 for (p1,p2) in opposing_players), name=f'no_opp_{gw}')

    if options.get("pick_prices") is not None:
        buffer = 0.2
        price_choices = options["pick_prices"]
        for (pos,val) in price_choices.items():
            if val == '':
                continue
            price_points = [float(i) for i in val.split(',')]
            value_dict = {i: price_points.count(i) for i in set(price_points)}
            con_iter = 0
            for key, count in value_dict.items():
                target_players = [p for p in players if merged_data.loc[p, 'Pos'] == pos and buy_price[p] >= key - buffer and buy_price[p] <= key + buffer]
                model.add_constraints((so.expr_sum(squad[p,w] for p in target_players) >= count for w in gameweeks), name=f'price_point_{pos}_{con_iter}')
                con_iter += 1
                
    if len(options.get("no_chip_gws", [])) > 0:
        no_chip_gws = options['no_chip_gws']
        model.add_constraint(so.expr_sum(use_bb[w] + use_wc[w] + use_fh[w] for w in no_chip_gws) == 0, name='no_chip_gws')

    # Objectives
    gw_xp = {w: so.expr_sum(points_player_week[p,w] * (lineup[p,w] + captain[p,w] + 0.1*vicecap[p,w] + so.expr_sum(bench_weights[o] * bench[p,w,o] for o in order)) for p in players) for w in gameweeks}
    gw_total = {w: gw_xp[w] - 4 * penalized_transfers[w] + ft_value * free_transfers[w] + itb_value * in_the_bank[w] for w in gameweeks}
    if objective == 'regular':
        total_xp = so.expr_sum(gw_total[w] for w in gameweeks)
        model.set_objective(-total_xp, sense='N', name='total_regular_xp')
    else:
        decay_objective = so.expr_sum(gw_total[w] * pow(decay_base, w-next_gw) for w in gameweeks)
        model.set_objective(-decay_objective, sense='N', name='total_decay_xp')

    iteration = options.get("iteration", 1)
    iteration_criteria = options.get("iteration_criteria", "this_gw_transfer_in")
    solutions = []

    for iter in range(iteration):

        # Solve
        tmp_folder = Path() / "tmp"
        tmp_folder.mkdir(exist_ok=True, parents=True)
        model.export_mps(f'tmp/{problem_name}_{problem_id}_{iter}.mps')
        print(f"Exported problem with name: {problem_name}_{problem_id}_{iter}")

        t0 = time.time()
        time.sleep(0.5)

        if options.get('export_debug', False) is True:
            with open("debug.sas", "w") as file:
                file.write(model.to_optmodel())

        use_cmd = options.get('use_cmd', False)

        solver = options.get('solver', 'cbc')

        if solver == 'cbc':

            if options.get('single_solve') is True:

                gap = options.get('gap', 0)
                secs = options.get('secs', 20*60)

                command = f'cbc tmp/{problem_name}_{problem_id}_{iter}.mps cost column ratio {gap} sec {secs} solve solu tmp/{problem_name}_{problem_id}_{iter}_sol.txt'
                if use_cmd:
                    os.system(command)
                else:
                    process = Popen(command, shell=False)
                    process.wait()

            else:

                command = f'cbc tmp/{problem_name}_{problem_id}_{iter}.mps cost column ratio 1 solve solu tmp/{problem_name}_{problem_id}_{iter}_sol_init.txt'
                if use_cmd:
                    os.system(command)
                else:
                    process = Popen(command, shell=False)
                    process.wait()
                secs = options.get('secs', 20*60)
                command = f'cbc tmp/{problem_name}_{problem_id}_{iter}.mps mips tmp/{problem_name}_{problem_id}_{iter}_sol_init.txt cost column sec {secs} solve solu tmp/{problem_name}_{problem_id}_{iter}_sol.txt'
                if use_cmd:
                    os.system(command)
                else:
                    process = Popen(command, shell=False) # add 'stdout=DEVNULL' for disabling logs
                    process.wait()

            # Popen fix with split?

            t1 = time.time()
            print(t1-t0, "seconds passed")

            # Parsing
            with open(f'tmp/{problem_name}_{problem_id}_{iter}_sol.txt', 'r') as f:
                for v in model.get_variables():
                    v.set_value(0)
                for line in f:
                    words = line.split()
                    if words[0] == 'Infeasible':
                        raise ValueError("Infeasible problem instance, check your parameters")
                    if 'objective value' in line:
                        continue
                    var = model.get_variable(words[1])
                    var.set_value(float(words[2]))

        elif solver == 'highs':

            highs_exec = options.get('solver_path', 'highs')

            secs = options.get('secs', 20*60)
            presolve = options.get('presolve', 'off')

            command = f'{highs_exec} --presolve {presolve} --model_file tmp/{problem_name}_{problem_id}_{iter}.mps --time_limit {secs} --solution_file tmp/{problem_name}_{problem_id}_{iter}_sol.txt'
            if use_cmd:
                os.system(command)
            else:
                process = Popen(command, shell=False)
                process.wait()

            # Parsing
            with open(f'tmp/{problem_name}_{problem_id}_{iter}_sol.txt', 'r') as f:
                for v in model.get_variables():
                    v.set_value(0)
                cols_started = False
                for line in f:
                    if not cols_started and "# Columns" not in line:
                        continue
                    elif "# Columns" in line:
                        cols_started = True
                        continue
                    elif cols_started and line[0] != "#":
                        words = line.split()
                        v = model.get_variable(words[0])
                        try:
                            if v.get_type() == so.INT:
                                v.set_value(round(float(words[1])))
                            elif v.get_type() == so.BIN:
                                v.set_value(round(float(words[1])))
                            elif v.get_type() == so.CONT:
                                v.set_value(round(float(words[1]),3))
                        except:
                            print("Error", words[0], line)
                    elif line[0] == "#":
                        break

        # DataFrame generation
        picks = []
        for w in gameweeks:
            for p in players:
                if squad[p,w].get_value() + squad_fh[p,w].get_value() + transfer_out[p,w].get_value() > 0.5:
                    lp = merged_data.loc[p]
                    is_captain = 1 if captain[p,w].get_value() > 0.5 else 0
                    is_squad = 1 if (use_fh[w].get_value() < 0.5 and squad[p,w].get_value() > 0.5) or (use_fh[w].get_value() > 0.5 and squad_fh[p,w].get_value() > 0.5) else 0
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
                    multiplier = 1*(is_lineup==1) + 1*(is_captain==1)
                    xp_cont = points_player_week[p,w] * multiplier
                    
                    picks.append([
                        w, lp['web_name'], position, lp['element_type'], lp['name'], player_buy_price, player_sell_price, round(points_player_week[p,w],2), minutes_player_week[p,w], is_squad, is_lineup, bench_value, is_captain, is_vice, is_transfer_in, is_transfer_out, multiplier, xp_cont
                    ])

        picks_df = pd.DataFrame(picks, columns=['week', 'name', 'pos', 'type', 'team', 'buy_price', 'sell_price', 'xP', 'xMin', 'squad', 'lineup', 'bench', 'captain', 'vicecaptain', 'transfer_in', 'transfer_out', 'multiplier', 'xp_cont']).sort_values(by=['week', 'lineup', 'type', 'xP'], ascending=[True, False, True, True])
        total_xp = so.expr_sum((lineup[p,w] + captain[p,w]) * points_player_week[p,w] for p in players for w in gameweeks).get_value()

        picks_df.sort_values(by=['week', 'squad', 'lineup', 'bench', 'type'], ascending=[True, False, False, True, True], inplace=True)

        # Writing summary
        summary_of_actions = ""
        move_summary = {'buy': [], 'sell': []}
        cumulative_xpts = 0
        for w in gameweeks:
            summary_of_actions += f"** GW {w}:\n"
            chip_decision = ("WC" if use_wc[w].get_value() > 0.5 else "") + ("FH" if use_fh[w].get_value() > 0.5 else "") + ("BB" if use_bb[w].get_value() > 0.5 else "")
            if chip_decision != "":
                summary_of_actions += "CHIP " + chip_decision + "\n"
            summary_of_actions += f"ITB={in_the_bank[w].get_value()}, FT={free_transfers[w].get_value()}, PT={penalized_transfers[w].get_value()}, NT={number_of_transfers[w].get_value()}\n"
            for p in players:
                if transfer_in[p,w].get_value() > 0.5:
                    summary_of_actions += f"Buy {p} - {merged_data['web_name'][p]}\n"
                    if w == next_gw:
                        move_summary['buy'].append(merged_data['web_name'][p])
            for p in players:
                if transfer_out[p,w].get_value() > 0.5:
                    summary_of_actions += f"Sell {p} - {merged_data['web_name'][p]}\n"
                    if w == next_gw:
                        move_summary['sell'].append(merged_data['web_name'][p])

            lineup_players = picks_df[(picks_df['week'] == w) & (picks_df['lineup'] == 1)]
            bench_players = picks_df[(picks_df['week'] == w) & (picks_df['bench'] >= 0)]

            # captain_name = picks_df[(picks_df['week'] == w) & (picks_df['captain'] == 1)].iloc[0]['name']
            # vicecap_name = picks_df[(picks_df['week'] == w) & (picks_df['vicecaptain'] == 1)].iloc[0]['name']

            summary_of_actions += "---\nLineup: \n"

            def get_display(row):
                return f"{row['name']} ({row['xP']}{', C' if row['captain'] == 1 else ''}{', V' if row['vicecaptain'] == 1 else ''})"

            for type in [1,2,3,4]:
                type_players = lineup_players[lineup_players['type'] == type]
                entries = type_players.apply(get_display, axis=1)
                summary_of_actions += '\t' + ', '.join(entries.tolist()) + "\n"
            summary_of_actions += "Bench: \n\t" + ', '.join(bench_players['name'].tolist()) + "\n"
            summary_of_actions += "Lineup xPts: " + str(round(lineup_players['xp_cont'].sum(),2)) + "\n---\n\n"
            cumulative_xpts = cumulative_xpts + round(lineup_players['xp_cont'].sum(),2)
        print("Cumulative xPts: " + str(round(cumulative_xpts,2)) + "\n---\n\n")

        if options.get('delete_tmp'):
            os.unlink(f"tmp/{problem_name}_{problem_id}_{iter}.mps")
            os.unlink(f"tmp/{problem_name}_{problem_id}_{iter}_sol.txt")


        buy_decisions = ', '.join(move_summary['buy'])
        sell_decisions = ', '.join(move_summary['sell'])
        if buy_decisions == '':
            buy_decisions = '-'
        if sell_decisions == '':
            sell_decisions = '-'

        if iteration == 1:
            return [{'iter': iter, 'model': model, 'picks': picks_df, 'total_xp': total_xp, 'summary': summary_of_actions, 'buy': buy_decisions, 'sell': sell_decisions, 'score': -model.get_objective_value()}]

        # Add current solution to a list, and add a new cut
        solutions.append({'iter': iter, 'model': model, 'picks': picks_df, 'total_xp': total_xp, 'summary': summary_of_actions, 'buy': buy_decisions, 'sell': sell_decisions, 'score': -model.get_objective_value()})
        if iteration_criteria == 'this_gw_transfer_in':
            actions = so.expr_sum(1-transfer_in[p, next_gw] for p in players if transfer_in[p, next_gw].get_value() > 0.5) \
                    + so.expr_sum(transfer_in[p, next_gw] for p in players if transfer_in[p, next_gw].get_value() < 0.5)
        elif iteration_criteria == 'this_gw_transfer_in_out':
            actions = so.expr_sum(1-transfer_in[p, next_gw] for p in players if transfer_in[p, next_gw].get_value() > 0.5) \
                    + so.expr_sum(transfer_in[p, next_gw] for p in players if transfer_in[p, next_gw].get_value() < 0.5) \
                    + so.expr_sum(1-transfer_out[p, next_gw] for p in players if transfer_out[p, next_gw].get_value() > 0.5) \
                    + so.expr_sum(transfer_out[p, next_gw] for p in players if transfer_out[p, next_gw].get_value() < 0.5)
        model.add_constraint(actions >= 1, name=f'cutoff_{iter}')

    return solutions

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

