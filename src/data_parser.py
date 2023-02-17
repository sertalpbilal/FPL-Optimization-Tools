from unicodedata import combining, normalize
import pandas as pd
import requests
from fuzzywuzzy import fuzz
import numpy as np


def read_data(options, source, weights=None):
    if source == 'review':
        data = pd.read_csv(options.get('data_path', '../data/fplreview.csv'))
        data['review_id'] = data['ID']
        return data
    elif source == 'review-odds':
        data = pd.read_csv(options.get('data_path', '../data/fplreview-odds.csv'))
        data['review_id'] = data['ID']
        return data
    elif source == 'kiwi':
        kiwi_data = pd.read_csv(options.get('kiwi_data_path', '../data/kiwi.csv'))
        kiwi_data['review_id'] = kiwi_data['ID']
        return rename_kiwi_columns(kiwi_data)
    elif source == 'mikkel':
        convert_mikkel_to_review(options.get('mikkel_data_path', '../data/TransferAlgorithm.csv'))
        data = pd.read_csv('../data/mikkel.csv')
        data['ID'] = data['review_id']
        return data
    elif source == 'mixed':
        # Get each source separately and mix with given weights
        all_data = []
        for (name, weight) in weights.items():
            if (weight == 0):
                continue
            df = read_data(options, name, None)
            # drop players without data
            first_gw_col = None
            for col in df.columns:
                if '_Pts' in col:
                    first_gw_col = col
                    break
            # drop missing ones
            df = df[~df[first_gw_col].isnull()].copy()
            for col in df.columns:
                if '_Pts' in col:
                    df[col.split('_')[0] + '_weight'] = weight
            all_data.append(df)
        
        # Update EV by weight
        new_data = []
        # for d, w in zip(data, data_weights):
        for d in all_data:
            pts_columns = [i for i in d if '_Pts' in i]
            min_columns = [i for i in d if '_xMins' in i]
            weights_cols = [i.split('_')[0] + '_weight' for i in pts_columns]
            # d[pts_columns] = d[pts_columns].multiply(d[weights_cols], axis='index')
            d[pts_columns] = pd.DataFrame(d[pts_columns].values * d[weights_cols].values, columns=d[pts_columns].columns, index=d[pts_columns].index)
            weights_cols = [i.split('_')[0] + '_weight' for i in min_columns]
            d[min_columns] = pd.DataFrame(d[min_columns].values * d[weights_cols].values, columns=d[min_columns].columns, index=d[min_columns].index)
            new_data.append(d.copy())

        combined_data = pd.concat(new_data, ignore_index=True)
        combined_data = combined_data.copy()
        combined_data['real_id'] = combined_data['review_id']
        combined_data.reset_index(drop=True, inplace=True)

        key_dict = {}
        for i in combined_data.columns.to_list():
            if '_weight' in i: # weight column
                key_dict[i] = 'sum'
            elif "_xMins" in i:
                key_dict[i] = 'sum'
            elif '_Pts' in i:
                key_dict[i] = 'sum'
            else:
                key_dict[i] = 'first'

        # key_dict = {i: 'first' if ("_x" not in i and "_P" not in i) else 'median' for i in main_keys}
        grouped_data = combined_data.groupby('real_id').agg(key_dict)
        final_data = grouped_data[grouped_data['review_id'] != 0].copy()
        # adjust by weight sum for each player
        for c in final_data.columns:
            if '_Pts' in c or '_xMins' in c:
                gw = c.split('_')[0]
                final_data[c] = final_data[c] / final_data[gw + '_weight']

        # Find missing players and add them

        r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
        players = r.json()['elements']
        existing_ids = final_data['review_id'].tolist()
        element_type_dict = {1: 'G', 2: 'D', 3: 'M', 4: 'F'}
        teams = r.json()['teams']
        team_code_dict = {i['code']: i for i in teams}
        missing_players = []
        for p in players:
            if p['id'] in existing_ids:
                continue
            missing_players.append({
                'fpl_id': p['id'],
                'review_id': p['id'],
                'ID': p['id'],
                'real_id': p['id'],
                'team': '',
                'Name': p['web_name'],
                'Pos': element_type_dict[p['element_type']],
                'Value': p['now_cost'] / 10,
                'Team': team_code_dict[p['team_code']]['name'],
                'Missing': 1
            })

        final_data = pd.concat([final_data, pd.DataFrame(missing_players)]).fillna(0)



        return final_data


# To remove accents in names
def fix_name_dialect(name):
    new_name = ''.join([c for c in normalize('NFKD', name) if not combining(c)])
    return new_name.replace('Ø', 'O').replace('ø', 'o').replace('ã', 'a')

def get_best_score(r):
    return max(r['wn_score'], r['cn_score'])

# To add FPL ID column to Mikkel's data and clean empty rows
def fix_mikkel(file_address):
    df = pd.read_csv(file_address, encoding='latin1')
    # Fix column names
    df.columns = df.columns.str.strip()
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

    df['BCV_clean'] = df['BCV'].astype(str).str.replace('\((.*)\)', '-\\1', regex=True).astype(str).str.strip()
    df['BCV_numeric'] = pd.to_numeric(df['BCV_clean'], errors='coerce')
    # drop -1 BCV
    df = df[df['BCV_numeric'] != -1].copy()
    df_cleaned = df[~((df['Player'] == '0') | (df['No.'].isnull()) | (df['BCV_numeric'].isnull()) | (df['No.'].isnull()))].copy()
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
    entries_df['score'] = entries_df[['wn_score', 'cn_score']].max(axis=1)
    entries_df['name_team'] = entries_df['player_input'] + ' @ ' + entries_df['team_input']
    entry_dict = entries_df.set_index('name_team')['id'].to_dict()
    fpl_name_dict = entries_df.set_index('id')['web_name'].to_dict()
    score_dict = entries_df.set_index('name_team')['score'].to_dict()
    df_cleaned['name_team'] = df_cleaned['Player'] + ' @ ' + df_cleaned['Team']
    df_cleaned['FPL ID'] = df_cleaned['name_team'].map(entry_dict)
    df_cleaned['fpl_name'] = df_cleaned['FPL ID'].map(fpl_name_dict)
    df_cleaned['score'] = df_cleaned['name_team'].map(score_dict)

    # Check for duplicate IDs
    duplicate_rows = df_cleaned['FPL ID'].duplicated(keep=False)
    if len(df_cleaned[duplicate_rows]) > 0:
        print("WARNING: There are players with duplicate IDs, lowest name match accuracy (score) will be dropped")
        print(df_cleaned[duplicate_rows][['Player', 'fpl_name', 'score']].head())
    df_cleaned.sort_values(by=['score'], ascending=[False], inplace=True)
    df_cleaned = df_cleaned[~df_cleaned['FPL ID'].duplicated(keep='first')].copy()
    df_cleaned.sort_index(inplace=True)

    print(len(df), len(df_cleaned))

    existing_ids = df_cleaned['FPL ID'].tolist()
    missing_players = []
    for p in players:
        if p['id'] in existing_ids:
            continue
        missing_players.append({
            'Position': element_type_dict[p['element_type']],
            'Player': p['web_name'],
            'Price': p['now_cost'] / 10,
            'FPL ID': p['id'],
            'Weighted minutes': 0,
            'Missing': 1
        })

    df_full = pd.concat([df_cleaned, pd.DataFrame(missing_players)]).fillna(0)

    # df_full.to_csv("debug.csv")

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

    raw_data['Price'] = pd.to_numeric(raw_data['Price'], errors='coerce')
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


def rename_kiwi_columns(review_data):
    # Rename column headers if the projections are from FPL Kiwi
    for col_name in review_data.columns:
        if ' ' in col_name:
            kiwi_category = col_name.split(' ')[0]
            if kiwi_category == 'xMin':
                kiwi_category = 'xMins'
            elif kiwi_category == 'xPts':
                kiwi_category = 'Pts'
            kiwi_week = col_name.split(' ')[1]
            review_data.rename(columns = {col_name : f'{kiwi_week}_{kiwi_category}'}, inplace=True)
    return review_data

def get_kiwi_review_avg(gw, review_data, kiwi_data):
    joined = kiwi_data.set_index('ID', drop=False).join(review_data.set_index('ID', drop=False), how='inner', lsuffix='_kiw', rsuffix='_rev')
    fplrev_gws = range(gw, min(39, gw+5))
    for gw in fplrev_gws:
        # if gw data is present in kiwi data take avg else take fplreview data
        if f'xPts {gw}' in kiwi_data.columns.to_list():
            joined[f'{gw} avg pts'] = (joined[f'xPts {gw}'] + joined[f'{gw}_Pts'])/2
            joined[f'{gw} avg mins'] = (joined[f'xMin {gw}'] + joined[f'{gw}_xMins'])/2
        else:
            joined[f'{gw} avg pts'] = joined[f'{gw}_Pts']
            joined[f'{gw} avg mins'] = joined[f'{gw}_xMins']
    cols = ['Pos_rev', 'ID_rev', 'Name_rev', 'BV', 'SV', 'Team_rev']\
         + sorted(([f'{gw} avg pts' for gw in fplrev_gws] + [f'{gw} avg mins' for gw in fplrev_gws]), \
            key=lambda desc : (int(desc.split(' ')[0]), desc.split(' ')[-1]))

    new_df = joined[cols]
    new_df.columns = review_data.columns
    return new_df


# convert_mikkel_to_review("../data/TransferAlgorithm.csv")
