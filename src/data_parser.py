from unicodedata import combining, normalize

import numpy as np
import pandas as pd
import requests
from fuzzywuzzy import fuzz


def _process_review_data(data, discard_am=False):
    """Process review data with optional AM filtering."""
    if discard_am:
        data = data[data["Pos"] != "AM"].copy()
        data["review_id"] = data["review_id"].astype(np.int64)
        for col in data.columns:
            if "_xMins" in col:
                data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0).astype(int)
    return data


def _get_mixed_source_data(options, weights):
    """Get data from multiple sources with weights."""
    all_data = []
    for name, weight in weights.items():
        if weight == 0:
            continue
        df = read_data(options, name, weights=None, discard_am=False)
        # drop players without data
        first_gw_col = None
        for col in df.columns:
            if "_Pts" in col:
                first_gw_col = col
                break
        # drop missing ones
        df = df[~df[first_gw_col].isnull()].copy()
        for col in df.columns:
            if "_Pts" in col:
                df[col.split("_")[0] + "_weight"] = weight
        all_data.append(df)
    return all_data


def _process_mixed_data(all_data):
    """Process mixed data by filtering AM players and converting data types."""
    # Separate AM columns
    am_data = [i[i["Pos"] == "AM"].copy() for i in all_data]
    for i, d in enumerate(all_data):
        filtered_d = d[d["Pos"] != "AM"].copy()
        filtered_d["review_id"] = filtered_d["review_id"].astype(np.int64)

        for col in filtered_d.columns:
            if "_xMins" in col:
                filtered_d[col] = pd.to_numeric(filtered_d[col], errors="coerce").fillna(0).astype(int)

        all_data[i] = filtered_d
    return all_data, am_data


def _apply_weights_to_data(all_data):
    """Apply weights to points and minutes columns."""
    new_data = []
    for d in all_data:
        pts_columns = [i for i in d if "_Pts" in i]
        min_columns = [i for i in d if "_xMins" in i]
        weights_cols = [i.split("_")[0] + "_weight" for i in pts_columns]
        d[pts_columns] = pd.DataFrame(
            d[pts_columns].values * d[weights_cols].values,
            columns=d[pts_columns].columns,
            index=d[pts_columns].index,
        )
        weights_cols = [i.split("_")[0] + "_weight" for i in min_columns]
        d[min_columns] = pd.DataFrame(
            d[min_columns].values * d[weights_cols].values,
            columns=d[min_columns].columns,
            index=d[min_columns].index,
        )
        new_data.append(d.copy())
    return new_data


def _combine_and_group_data(new_data):
    """Combine data and group by real_id."""
    combined_data = pd.concat(new_data, ignore_index=True)
    combined_data = combined_data.copy()
    combined_data["real_id"] = combined_data["review_id"]
    combined_data.reset_index(drop=True, inplace=True)

    key_dict = {}
    for i in combined_data.columns.to_list():
        if "_weight" in i:  # weight column
            key_dict[i] = "sum"
        elif "_xMins" in i:
            key_dict[i] = "sum"
        elif "_Pts" in i:
            key_dict[i] = "sum"
        else:
            key_dict[i] = "first"

    grouped_data = combined_data.groupby("real_id").agg(key_dict)
    final_data = grouped_data[grouped_data["review_id"] != 0].copy()

    # adjust by weight sum for each player
    for c in final_data.columns:
        if "_Pts" in c or "_xMins" in c:
            gw = c.split("_")[0]
            final_data[c] = final_data[c] / final_data[gw + "_weight"]

    return final_data


def _add_missing_players(final_data):
    """Add missing players from FPL API."""
    r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    players = r.json()["elements"]
    existing_ids = final_data["review_id"].tolist()
    element_type_dict = {1: "G", 2: "D", 3: "M", 4: "F"}
    teams = r.json()["teams"]
    team_code_dict = {i["code"]: i for i in teams}
    missing_players = []
    for p in players:
        if p["id"] in existing_ids:
            continue
        missing_players.append(
            {
                "fpl_id": p["id"],
                "review_id": p["id"],
                "ID": p["id"],
                "real_id": p["id"],
                "team": "",
                "Name": p["web_name"],
                "Pos": element_type_dict[p["element_type"]],
                "Value": p["now_cost"] / 10,
                "Team": team_code_dict[p["team_code"]]["name"],
                "Missing": 1,
            }
        )

    return pd.concat([final_data, pd.DataFrame(missing_players)]).fillna(0)


def _add_am_data_if_requested(final_data, am_data, options):
    """Add AM data if export_am_ev option is enabled."""
    if options.get("export_am_ev"):
        for d in am_data:
            if len(d) > 0:
                am_first = d[["Pos", "ID", "Name", "BV", "SV", "Team"] + [c for c in d.columns if "_Pts" in c]]
                final_data = pd.concat([final_data, am_first])
                final_data.fillna(0, inplace=True)
                break
    return final_data


def read_data(options, source, weights=None, discard_am=False):
    if source == "review":
        if options.get("binary_file_name"):
            data_path = "../data/" + options.get("binary_file_name") + ".csv"
        else:
            data_path = options.get("data_path", "../data/fplreview.csv")
        data = pd.read_csv(data_path)
        data["review_id"] = data["ID"]
        return _process_review_data(data, discard_am)

    elif source == "review-odds":
        data = pd.read_csv(options.get("data_path", "../data/fplreview-odds.csv"))
        data["review_id"] = data["ID"]
        return _process_review_data(data, discard_am)

    elif source == "mikkel":
        convert_mikkel_to_review(options.get("mikkel_data_path", "../data/TransferAlgorithm.csv"))
        data = pd.read_csv("../data/mikkel.csv")
        data["ID"] = data["review_id"]
        return data

    elif source == "mixed":
        # Get each source separately and mix with given weights
        all_data = _get_mixed_source_data(options, weights)
        all_data, am_data = _process_mixed_data(all_data)
        new_data = _apply_weights_to_data(all_data)
        final_data = _combine_and_group_data(new_data)
        final_data = _add_missing_players(final_data)
        final_data = _add_am_data_if_requested(final_data, am_data, options)
        return final_data


# To remove accents in names
def fix_name_dialect(name):
    new_name = "".join([c for c in normalize("NFKD", name) if not combining(c)])
    return new_name.replace("Ø", "O").replace("ø", "o").replace("ã", "a")


def get_best_score(r):
    return max(r["wn_score"], r["cn_score"])


def _get_fpl_data():
    """Fetch FPL API data and create team mappings."""
    r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    players = r.json()["elements"]
    teams = r.json()["teams"]

    mikkel_team_dict = {
        "BHA": "BRI",
        "CRY": "CPL",
        "NFO": "NOT",
        "WHU": "WHM",
        "SHU": "SHE",
    }

    for t in teams:
        t["mikkel_short"] = mikkel_team_dict.get(t["short_name"], t["short_name"])

    return players, teams


def _clean_mikkel_data(df):
    """Clean and preprocess Mikkel data."""
    df.columns = df.columns.str.strip()

    # Clean BCV column
    df["BCV_clean"] = df["BCV"].astype(str).str.replace(r"\((.*)\)", "-\\1", regex=True).astype(str).str.strip()
    df["BCV_numeric"] = pd.to_numeric(df["BCV_clean"], errors="coerce")

    # Filter out invalid data
    df = df[df["BCV_numeric"] != -1].copy()
    df_cleaned = df[~((df["Player"] == "0") | (df["No."].isnull()) | (df["BCV_numeric"].isnull()) | (df["No."].isnull()))].copy()

    # Clean names and fix team/position mappings
    df_cleaned["Clean_Name"] = df_cleaned["Player"].apply(fix_name_dialect)
    mikkel_team_fix = {"WHU": "WHM", "SHU": "SHE"}
    df_cleaned["Team"] = df_cleaned["Team"].replace(mikkel_team_fix)
    df_cleaned["Position"] = df_cleaned["Position"].replace({"GK": "G"})

    # Drop players without team name
    df_cleaned.dropna(subset=["Team"], inplace=True)

    return df_cleaned


def _create_player_matching_data(players, teams):
    """Create player data for name matching."""
    element_type_dict = {1: "G", 2: "D", 3: "M", 4: "F"}
    team_code_dict = {i["code"]: i for i in teams}

    player_names = [
        {
            "id": e["id"],
            "web_name": e["web_name"],
            "combined": e["first_name"] + " " + e["second_name"],
            "team": team_code_dict[e["team_code"]]["mikkel_short"],
            "position": element_type_dict[e["element_type"]],
        }
        for e in players
    ]

    for target in player_names:
        target["wn"] = fix_name_dialect(target["web_name"])
        target["cn"] = fix_name_dialect(target["combined"])

    return player_names


def _match_players_to_fpl(df_cleaned, player_names):
    """Match Mikkel players to FPL players using fuzzy matching."""
    entries = []
    for player in df_cleaned.iloc:
        possible_matches = [i for i in player_names if i["team"] == player["Team"] and i["position"] == player["Position"]]

        for target in possible_matches:
            p = player["Clean_Name"]
            target["wn_score"] = fuzz.token_set_ratio(p, target["wn"])
            target["cn_score"] = fuzz.token_set_ratio(p, target["cn"])

        best_match = max(possible_matches, key=get_best_score)
        entries.append(
            {
                "player_input": player["Player"],
                "team_input": player["Team"],
                "position_input": player["Position"],
                **best_match,
            }
        )

    return entries


def _process_matched_entries(entries, df_cleaned):
    """Process matched entries and create mapping dictionaries."""
    entries_df = pd.DataFrame(entries)
    entries_df["score"] = entries_df[["wn_score", "cn_score"]].max(axis=1)
    entries_df["name_team"] = entries_df["player_input"] + " @ " + entries_df["team_input"]

    entry_dict = entries_df.set_index("name_team")["id"].to_dict()
    fpl_name_dict = entries_df.set_index("id")["web_name"].to_dict()
    score_dict = entries_df.set_index("name_team")["score"].to_dict()

    df_cleaned["name_team"] = df_cleaned["Player"] + " @ " + df_cleaned["Team"]
    df_cleaned["FPL ID"] = df_cleaned["name_team"].map(entry_dict)
    df_cleaned["fpl_name"] = df_cleaned["FPL ID"].map(fpl_name_dict)
    df_cleaned["score"] = df_cleaned["name_team"].map(score_dict)

    return df_cleaned


def _handle_duplicates_and_sort(df_cleaned, original_len):
    """Handle duplicate IDs and sort by score."""
    duplicate_rows = df_cleaned["FPL ID"].duplicated(keep=False)
    if len(df_cleaned[duplicate_rows]) > 0:
        print("WARNING: There are players with duplicate IDs, lowest name match accuracy (score) will be dropped")
        # print(df_cleaned[duplicate_rows][["Player", "fpl_name", "score"]].head())

    df_cleaned.sort_values(by=["score"], ascending=[False], inplace=True)
    df_cleaned = df_cleaned[~df_cleaned["FPL ID"].duplicated(keep="first")].copy()
    df_cleaned.sort_index(inplace=True)
    return df_cleaned


def _add_missing_players_to_mikkel(df_cleaned, players):
    """Add missing FPL players to the dataset."""
    element_type_dict = {1: "G", 2: "D", 3: "M", 4: "F"}
    existing_ids = df_cleaned["FPL ID"].tolist()
    missing_players = []

    for p in players:
        if p["id"] in existing_ids:
            continue
        missing_players.append(
            {
                "Position": element_type_dict[p["element_type"]],
                "Player": p["web_name"],
                "Price": p["now_cost"] / 10,
                "FPL ID": p["id"],
                "Weighted minutes": 0,
                "Missing": 1,
            }
        )

    df_full = pd.concat([df_cleaned, pd.DataFrame(missing_players)]).fillna(0)
    return df_full


def fix_mikkel(file_address):
    """Fix and process Mikkel data by matching players to FPL IDs."""
    # Load and get FPL data
    df = pd.read_csv(file_address, encoding="latin1")
    players, teams = _get_fpl_data()

    # Clean the data
    df_cleaned = _clean_mikkel_data(df)
    original_len = len(df)

    # Create player matching data
    player_names = _create_player_matching_data(players, teams)

    # Match players to FPL IDs
    entries = _match_players_to_fpl(df_cleaned, player_names)

    # Process matched entries
    df_cleaned = _process_matched_entries(entries, df_cleaned)

    # Handle duplicates and sort
    df_cleaned = _handle_duplicates_and_sort(df_cleaned, original_len)

    # Add missing players
    df_full = _add_missing_players_to_mikkel(df_cleaned, players)

    return df_full


# To convert cleaned Mikkel data into Review format
def convert_mikkel_to_review(target):
    # Read and add ID column
    raw_data = fix_mikkel(target)

    static_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    r = requests.get(static_url).json()
    teams = r["teams"]

    new_names = {i: i.strip() for i in raw_data.columns}
    raw_data.rename(columns=new_names, inplace=True)

    raw_data["Price"] = pd.to_numeric(raw_data["Price"], errors="coerce")
    max_price = 20
    df_clean = raw_data[raw_data["Price"] < max_price].copy()
    df_clean["Weighted minutes"].fillna("90", inplace=True)
    df_clean["review_id"] = df_clean["FPL ID"].astype(int)

    pos_fix = {"GK": "G"}
    df_clean["Pos"] = df_clean["Position"]
    df_clean["Pos"] = df_clean["Pos"].replace(pos_fix)

    df_clean.loc[df_clean["Pos"].isin(["G", "D"]), "Weighted minutes"] = "90"

    gws = []
    for i in df_clean.columns:
        try:
            int(i)
            df_clean[f"{i}_Pts"] = df_clean[i].str.strip().replace({"-": 0}).astype(float)
            df_clean[f"{i}_xMins"] = df_clean["Weighted minutes"].str.strip().replace({"-": 0}).astype(float).replace({np.nan: 0})
            gws.append(i)
        except Exception:
            continue
    df_clean["Name"] = df_clean["Player"]
    df_clean["Value"] = df_clean["Price"]

    df_final = df_clean[["review_id", "Name", "Pos", "Value"] + [f"{gw}_{tag}" for gw in gws for tag in ["Pts", "xMins"]]].copy()
    df_final.replace({"-": 0}, inplace=True)
    elements_data = r["elements"]
    player_ids = [i["id"] for i in elements_data]
    player_names = {i["id"]: i["web_name"] for i in elements_data}
    player_pos = {i["id"]: i["element_type"] for i in elements_data}
    player_price = {i["id"]: i["now_cost"] / 10 for i in elements_data}
    pos_no = {1: "G", 2: "D", 3: "M", 4: "F"}
    values = []
    existing_players = df_final["review_id"].to_list()
    for i in player_ids:
        if i not in existing_players:
            entry = {
                "review_id": i,
                "Name": player_names[i],
                "Pos": pos_no[player_pos[i]],
                "Value": player_price[i],
                **{f"{gw}_{tag}": 0 for gw in gws for tag in ["Pts", "xMins"]},
            }
            values.append(entry)

    team_data = teams
    team_dict = {i["code"]: i["name"] for i in team_data}
    player_teams = {i["id"]: team_dict[i["team_code"]] for i in elements_data}
    # Add missing players
    # df_final = pd.concat([df_final, pd.DataFrame(values, columns=df_final.columns)], ignore_index=True)
    df_final["Team"] = df_final["review_id"].map(player_teams)

    df_final["fpl_id"] = df_final["review_id"]

    df_final["Name"] = df_final["review_id"].replace(player_names)

    df_final.set_index("fpl_id", inplace=True)
    df_final.to_csv("../data/mikkel.csv")


# convert_mikkel_to_review("../data/TransferAlgorithm.csv")
