import pandas as pd
import sasoptpy as so
import requests
import json
import os
import random
from subprocess import Popen
# from IPython.display import display, HTML
from math import exp
import string
from pathlib import Path
import glob
import time

Path("tmp/").mkdir(parents=True, exist_ok=True)
all_files = glob.glob("tmp/*")
for f in all_files:
    os.unlink(f)

def get_random_id(n):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

ratings = pd.read_csv("https://projects.fivethirtyeight.com/soccer-api/club/spi_global_rankings.csv")
ratings.head()

hfa = 0.15
fixture = pd.read_excel("../data/ben_2021_22.xlsx", sheet_name="HA Schedule", header=2, index_col=0, usecols=range(1, 41), engine='openpyxl').drop(columns=["Unnamed: 2"])
fixture.index.name ='team'
fixture_original = fixture.copy()
fix_dict = fixture.to_dict('index')
fixture.head()

teams = {
    'ARS': {'name': 'Arsenal'},
    'AVL':  {'name': 'Aston Villa'},
    'BRE':  {'name': 'Brentford'},
    'BHA':  {'name': 'Brighton and Hove Albion'},
    'BUR':  {'name': 'Burnley'},
    'CHE':  {'name': 'Chelsea'},
    'CRY':  {'name': 'Crystal Palace'},
    'EVE':  {'name': 'Everton'},
    'LEI':  {'name': 'Leicester City'},
    'LEE': {'name':  'Leeds United'},
    'LIV': {'name':  'Liverpool'},
    'MCI': {'name':  'Manchester City'},
    'MUN': {'name':  'Manchester United'},
    'NEW': {'name':  'Newcastle'},
    'NOR': {'name':  'Norwich City'},
    'SOU': {'name':  'Southampton'},
    'TOT': {'name':  'Tottenham Hotspur'},
    'WAT': {'name':  'Watford'},
    'WHU': {'name':  'West Ham United'},
    'WOL': {'name':  'Wolverhampton'}
}


for team, val in teams.items():
    rating = ratings.loc[ratings.name == val['name'], 'spi'].values[0]
    val['rating'] = rating

for team, val in teams.items():
    print(f"{team:.3s} {val['rating']:.1f}")

team_list = list(teams.keys())
gameweeks = list(range(1,39))

def get_fdr_with_hfa(hfa=0):
    fdr = {}
    for t in team_list:
        for w in range(1,39):
            opp = fix_dict[t][w]
            if opp.islower(): # AWAY
                fdr[t,w] = teams[opp.upper()]['rating'] * exp(hfa)
            else:
                fdr[t,w] = teams[fix_dict[t][w]]['rating'] / exp(hfa)
    return fdr

pd.set_option('display.max_columns', None) 

def read_solution(m, sol_file="fdr.sol"):
    with open(sol_file, 'r') as f:
        for v in m.get_variables():
            v.set_value(0)
        for line in f:
            if 'objective value' in line:
                continue
            words = line.split()
            v = m.get_variable(words[1])
            v.set_value(float(words[2]))

def print_solution(m, gws, fdr):
    pick_team = m.get_variable('pick_team')
    pick_team_gw = m.get_variable('pick_team_gw')
    # Print solution
    selected_teams = []
    gameweek_picks = []
    for t in team_list:
        entry = {'team': t}
        if pick_team[t].get_value() > 0:
            selected_teams.append(t)
            for g in gws:
                entry.update({g: round(pick_team_gw[t,g].get_value() * fdr[t,g], 3) })
            gameweek_picks.append(entry)
    
    # Print and first table - values
    print(f'\nSelected: {" and ".join(selected_teams)}. Total FDR: {round(m.get_objective_value(),3)}')
    pick_df = pd.DataFrame(gameweek_picks)
    s = pick_df.style
    colored_vals = lambda x: 'background-color: lightblue; color: black' if type(x) == float and x > 0 else 'color: white'
    s.applymap(colored_vals)
    # display(HTML(s.render().replace("000", "")))
    
    # Second table - names
    fr = fixture_original.reset_index()
    selected_fixture = fr[fr['team'].isin(selected_teams)].copy().reset_index(drop=True)
    selected_fixture = selected_fixture[['team'] + gws]
    s2 = selected_fixture.style
    def color_based_on_selection(cell):
        d = cell.copy()
        for c in d.columns:
            if c == 'team': continue
            for r in d.index:
                if pick_df.loc[r, c]:
                    d.loc[r, c] = 'background-color: green; color: white'
                else:
                    d.loc[r, c] = ''
        return d
    s2.apply(color_based_on_selection, axis=None)
    # display(HTML(s2.render()))
    return {'teams': selected_teams, 'values': pick_df, 'rotation': selected_fixture}

def solve_N_pick_K_pair_problem(N=3, K=2, max_iter=1, first_gw=1, last_gw=38, exclude=[], hfa=0.15):
    if last_gw > 38:
        return {"teams": [], "total_diff": "-", "avg_diff": "-"}
    fdr = get_fdr_with_hfa(hfa)
    problem_name = get_random_id(10)
    m = so.Model(name=f'N_K_rotation_problem_name')
    print(f"Name: {problem_name}, Params: N{N} K{K} fg{first_gw} lg{last_gw} hfa{hfa}")
    team_list = list(teams.keys())
    gameweeks = list(range(first_gw, last_gw+1))
    pick_team = m.add_variables(team_list, vartype=so.binary, name='pick_team')
    pick_team_gw = m.add_variables(team_list, gameweeks, vartype=so.binary, name='pick_team_gw')

    if len(exclude) > 0:
        m.add_constraints((pick_team[t] == 0 for t in exclude), name='disable_teams')

    m.add_constraint(so.expr_sum(pick_team[t] for t in team_list) == N, name='pick_2')
    m.add_constraints((so.expr_sum(pick_team_gw[t, g] for t in team_list) == K for g in gameweeks), name='pick_1_per_gw')
    m.add_constraints((pick_team_gw[t,g] <= pick_team[t] for t in team_list for g in gameweeks), name='valid_picks_only')

    # Force using each team at least once
    m.add_constraints((so.expr_sum(pick_team_gw[t,g] for g in gameweeks) >= pick_team[t] for t in team_list), name='force_use')

    m.set_objective(so.expr_sum(fdr[t, g] * pick_team_gw[t, g] for t in team_list for g in gameweeks), sense='N', name='total_fdr')

    m.export_mps(f"tmp/{problem_name}.mps")
    time.sleep(0.1)
    command = f"cbc tmp/{problem_name}.mps solve solu tmp/{problem_name}.sol"
    stout, sterr = Popen(command).communicate()
    read_solution(m, f'tmp/{problem_name}.sol')
    sol = print_solution(m, gameweeks, fdr)
    # for it in range(1, max_iter):
    #     c = m.add_constraint(so.expr_sum(pick_team[t] for t in selected_teams) <= N-1, name=f'cutoff_{it}')
    #     m.export_mps("fdr.mps")
    #     Popen(command).wait()
    #     read_solution(m, f'tmp/{problem_name}.sol')
    #     selected_teams = print_solution(m, gameweeks, fdr)

    return {'teams': sol['teams'], 'total_diff': m.get_objective_value(), 'avg_diff': m.get_objective_value()/(last_gw-first_gw+1)/K}

def wrapper(kwargs):
    return solve_N_pick_K_pair_problem(**kwargs)

if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from itertools import repeat
    N = 5
    K = 3
    gw_range = list(range(N,11))
    start_gw = list(range(1,39-N+1))
    all_pairs = [(sw, g) for sw in start_gw for g in gw_range]
    pair_names = [{'start_gw': f'GW{sw}', 'gw_range': g, 'last_gw': sw+g-1} for sw in start_gw for g in gw_range]
    ops = [{'N': N, 'K': K, 'first_gw': sw, 'last_gw': sw+g-1, 'max_iter': 1, 'hfa': 0.15} for sw in start_gw for g in gw_range]
    parallel = True
    if parallel:
        with ThreadPoolExecutor(max_workers=8) as executor:
            res = list(executor.map(wrapper, ops))
    else:
        res = []
        for o in ops:
            res.append(wrapper(o))

    all_res = list(zip(pair_names, res))
    for r in all_res:
        print(r)

    df_raw = [{**a, **b} for (a,b) in all_res]
    df = pd.DataFrame(df_raw)
    print(df)
    df['teams'] = df['teams'].str.join(" ")
    writer = pd.ExcelWriter(f'res/optimal_N{N}_K{K}.xlsx')
    pvt1 = df.groupby(['start_gw', 'gw_range'], sort=False)['teams'].first().unstack('gw_range')
    pvt2 = df.groupby(['start_gw', 'gw_range'], sort=False)['avg_diff'].first().unstack('gw_range')
    same_sheet = False
    if same_sheet:
        sheet1 = writer.book.add_worksheet("Solution")
        writer.sheets["Solution"] = sheet1
        pvt1.to_excel(writer, sheet_name="Solution")  # sheet_name='Teams')
        pvt2.to_excel(writer, sheet_name="Solution", startrow=0, startcol=12-N) # sheet_name='AvgRating')
    else:
        pvt1.to_excel(writer, sheet_name='Teams')
        pvt2.to_excel(writer, sheet_name='AvgRating')
    writer.save()

