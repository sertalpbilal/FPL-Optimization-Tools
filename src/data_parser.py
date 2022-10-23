from unicodedata import combining, normalize
import pandas as pd
import requests
from fuzzywuzzy import fuzz
import numpy as np

# To remove accents in names
def fix_name_dialect(name):
    new_name = ''.join([c for c in normalize('NFKD', name) if not combining(c)])
    return new_name.replace('Ø', 'O').replace('ø', 'o').replace('ã', 'a')

def get_best_score(r):
    return max(r['wn_score'], r['cn_score'])

# To add FPL ID column to Mikkel's data and clean empty rows
def fix_mikkel(file_address):
    df = pd.read_csv(file_address, encoding='latin1')
    remove_accents = fix_name_dialect
    r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    players = r.json()['elements']
    mikkel_team_dict = {
      'BHA': 'BRI',
      'CRY': 'CPL',
      'NFO': 'NOT',
      'SOU': 'SOT',
      'WHU': 'WHM'
    }
    teams = r.json()['teams']
    for t in teams:
        t['mikkel_short'] = mikkel_team_dict.get(t['short_name'], t['short_name'])

    df['BCV_clean'] = df[' BCV '].astype(str).str.replace('\((.*)\)', '-\\1', regex=True).astype(str).str.strip()
    df['BCV_numeric'] = pd.to_numeric(df['BCV_clean'], errors='coerce')
    df_cleaned = df[~((df['Player'] == '0') | (df['No.'].isnull()) | (df['BCV_numeric'].isnull()) | (df['No.'].isnull()))].copy()
    print(len(df), len(df_cleaned))
    df_cleaned['Clean_Name'] = df_cleaned['Player'].apply(remove_accents)
    df_cleaned.head()
    mikkel_team_fix = {'WHU': 'WHM'}
    df_cleaned['Team'] = df_cleaned['Team'].replace(mikkel_team_fix)
    df_cleaned['Position'] = df_cleaned['Position'].replace({'GK': 'G'})
    element_type_dict = {1: 'G', 2: 'D', 3: 'M', 4: 'F'}
    team_code_dict = {i['code']: i for i in teams}
    player_names = [{
        'id': e['id'],
        'web_name': e['web_name'],
        'combined': e['first_name'] + ' ' + e['second_name'],
        'team': team_code_dict[e['team_code']]['mikkel_short'],
        'position': element_type_dict[e['element_type']],
    } for e in players]
    for target in player_names:
        target['wn'] = remove_accents(target['web_name'])
        target['cn'] = remove_accents(target['combined'])

    entries = []
    for player in df_cleaned.iloc:
        possible_matches = [i for i in player_names if i['team'] == player['Team'] and i['position'] == player['Position']]
        for target in possible_matches:
            p = player['Clean_Name']
            target['wn_score'] = fuzz.token_set_ratio(p,target['wn'])
            target['cn_score'] = fuzz.token_set_ratio(p,target['cn'])

        best_match = max(possible_matches, key=get_best_score)
        entries.append({'player_input': player['Player'], 'team_input': player['Team'], 'position_input': player['Position'], **best_match})
        # print(player['Player'], player['Team'], best_match)

    entries_df = pd.DataFrame(entries)
    entries_df['name_team'] = entries_df['player_input'] + ' @ ' + entries_df['team_input']
    entry_dict = entries_df.set_index('name_team')['id'].to_dict()
    df_cleaned['name_team'] = df_cleaned['Player'] + ' @ ' + df_cleaned['Team']
    df_cleaned['FPL ID'] = df_cleaned['name_team'].map(entry_dict)

    existing_ids = df_cleaned['FPL ID'].tolist()
    missing_players = []
    for p in players:
        if p['id'] in existing_ids:
            continue
        missing_players.append({
            'Position': element_type_dict[p['element_type']],
            'Player': p['web_name'],
            ' Price ': p['now_cost'] / 10,
            'FPL ID': p['id'],
            ' Weighted minutes ': 0
        })

    df_full = pd.concat([df_cleaned, pd.DataFrame(missing_players)]).fillna(0)

    return df_full

# To convert cleaned Mikkel data into Review format
def convert_mikkel_to_review(target):

    # Read and add ID column
    raw_data = fix_mikkel(target)

    static_url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    r = requests.get(static_url).json()
    teams = r['teams']

    new_names = {i: i.strip() for i in raw_data.columns}
    raw_data.rename(columns=new_names, inplace=True)

    df_clean = raw_data[raw_data['Price'] < 20].copy()
    df_clean['Weighted minutes'].fillna('90', inplace=True)
    df_clean['review_id'] = df_clean['FPL ID'].astype(int)

    pos_fix = {'GK': 'G'}
    df_clean['Pos'] = df_clean['Position']
    df_clean['Pos'] = df_clean['Pos'].replace(pos_fix)

    df_clean.loc[df_clean['Pos'].isin(['G', 'D']), 'Weighted minutes'] = '90'

    gws = []
    for i in df_clean.columns:
        try:
            int(i)
            df_clean[f'{i}_Pts'] = df_clean[i].str.strip().replace({'-': 0}).astype(float)
            df_clean[f'{i}_xMins'] = df_clean['Weighted minutes'].str.strip().replace({'-': 0}).astype(float).replace({np.nan: 0})
            gws.append(i)
        except:
            continue
    df_clean['Name'] = df_clean['Player']
    df_clean['Value'] = df_clean['Price']

    df_final = df_clean[['review_id', 'Name', 'Pos', 'Value'] + [f'{gw}_{tag}' for gw in gws for tag in ['Pts', 'xMins']]].copy()
    df_final.replace({'-': 0}, inplace=True)
    elements_data = r['elements']
    player_ids = [i['id'] for i in elements_data]
    player_names = {i['id']: i['web_name'] for i in elements_data}
    player_pos = {i['id']: i['element_type'] for i in elements_data}
    player_price = {i['id']: i['now_cost']/10 for i in elements_data}
    pos_no = {1: 'G', 2: 'D', 3: 'M', 4: 'F'}
    values = []
    existing_players = df_final['review_id'].to_list()
    for i in player_ids:
        if i not in existing_players:
            entry = {'review_id': i, 'Name': player_names[i], 'Pos': pos_no[player_pos[i]], 'Value': player_price[i], **{f'{gw}_{tag}': 0 for gw in gws for tag in ['Pts', 'xMins']}}
            values.append(entry)

    team_data = teams
    team_dict = {i['code']: i['name'] for i in team_data}
    player_teams = {i['id']: team_dict[i['team_code']] for i in elements_data}
    # Add missing players
    # df_final = pd.concat([df_final, pd.DataFrame(values, columns=df_final.columns)], ignore_index=True)
    df_final['Team'] = df_final['review_id'].map(player_teams)

    df_final['fpl_id'] = df_final['review_id']

    df_final['Name'] = df_final['review_id'].replace(player_names)

    df_final.set_index('fpl_id', inplace=True)
    df_final.to_csv(f'../data/mikkel.csv')


# convert_mikkel_to_review("../data/TransferAlgorithm.csv")
