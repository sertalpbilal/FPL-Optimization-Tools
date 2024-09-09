import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from io import StringIO


def load_master_data(file_path):
    """Load and filter the master data."""
    try:
        master = pd.read_csv(file_path)
        master_filtered = master[master["24-25"].notna()]
        master_filtered = master_filtered[
            ["code", "fbref", "24-25", "first_name", "second_name", "web_name"]
        ]
        master_filtered = master_filtered.astype({"24-25": "int"})
        master_filtered = master_filtered.rename(columns={"24-25": "fpl_id"})
        return master_filtered
    except Exception as e:
        print(f"Error loading master data: {e}")
        return pd.DataFrame()


def load_all_players_data(file_path):
    """Load the all_players_prev_seasons data."""
    try:
        return pd.read_csv(file_path)
    except Exception as e:
        print(f"Error loading all players data: {e}")
        return pd.DataFrame()


def get_fpl_data():
    """Retrieve FPL data and process it."""
    try:
        r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
        fpl_data = r.json()

        elements = pd.DataFrame(fpl_data["elements"])
        elements = elements[
            ["id", "team", "element_type", "now_cost", "selected_by_percent"]
        ]
        elements["position"] = elements["element_type"].replace(
            {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
        )
        elements = elements.rename(columns={"selected_by_percent": "tsb"})
        elements["now_cost"] = np.round(elements["now_cost"] / 10, 1)

        teams = pd.DataFrame(fpl_data["teams"])
        teams = teams[["id", "name", "short_name"]]

        fpl_elements = elements.merge(teams, left_on="team", right_on="id", how="inner")
        fpl_elements = fpl_elements.rename(
            columns={"id_x": "fpl_id", "id_y": "team_id", "name": "team_name"}
        )
        fpl_elements = fpl_elements[
            [
                "fpl_id",
                "team_id",
                "team_name",
                "short_name",
                "element_type",
                "now_cost",
                "tsb",
                "position",
            ]
        ]
        return fpl_elements
    except Exception as e:
        print(f"Error retrieving FPL data: {e}")
        return pd.DataFrame()


def get_player_stats_new_season(url):
    """Retrieve player stats for the new season from the given URL."""
    try:
        soup = BeautifulSoup(
            requests.get(url).text.replace("<!--", "").replace("-->", ""), "html.parser"
        )
        table = soup.find("table", {"id": "stats_standard"})
        ids = [
            x["data-append-csv"] for x in table.find_all("td", {"data-stat": "player"})
        ]

        df = pd.read_html(StringIO(str(table)))[0]
        df.columns = [f"{i} {j}" if "Unnamed" not in i else j for i, j in df.columns]
        df = df.loc[df["Rk"] != "Rk"]
        df["fbref"] = ids

        df = df.rename(
            {
                "Playing Time MP": "MP",
                "Playing Time Starts": "Starts",
                "Playing Time Min": "Min",
                "Playing Time 90s": "90s",
                "Per 90 Minutes npxG": "npxG",
                "Per 90 Minutes xAG": "xAG",
            },
            axis=1,
        )
        df = df[
            [
                "fbref",
                "Player",
                "Squad",
                "Age",
                "MP",
                "Starts",
                "Min",
                "90s",
                "npxG",
                "xAG",
            ]
        ]
        df = df.astype(
            {
                "MP": "int",
                "Starts": "int",
                "Min": "int",
                "90s": "float64",
                "npxG": "float64",
                "xAG": "float64",
            }
        )

        return df
    except Exception as e:
        print(f"Error retrieving new season player stats: {e}")
        return pd.DataFrame()


def calculate_weighted_stats(fpl_players_df, weight_new_data=1.0):
    """Calculate weighted stats with additional weight for new data."""
    # Calculate total 90s for normalization
    total_90s = fpl_players_df["90s"] + fpl_players_df["90s_new"]

    # Apply additional weight to new data
    weight_old_data = 1.0
    weight_new_data = float(weight_new_data)

    fpl_players_df["weighted_npxG"] = (
        (fpl_players_df["npxG"] * fpl_players_df["90s"] / total_90s * weight_old_data)
        + (
            fpl_players_df["npxG_new"]
            * fpl_players_df["90s_new"]
            / total_90s
            * weight_new_data
        )
    ).round(2)

    fpl_players_df["weighted_xAG"] = (
        (fpl_players_df["xAG"] * fpl_players_df["90s"] / total_90s * weight_old_data)
        + (
            fpl_players_df["xAG_new"]
            * fpl_players_df["90s_new"]
            / total_90s
            * weight_new_data
        )
    ).round(2)


def main():
    weight_new_data = float(input("Enter the weight factor for new data: "))

    # Load data
    master_filtered = load_master_data(
        "C:/Users/erknud3/fpl-optimization/model/FPL-ID-Map/Master.csv"
    )
    all_players_prev_seasons = load_all_players_data(
        "C:/Users/erknud3/fpl-optimization/model/data/Historic_Data/all_players_prev_seasons.csv"
    )

    if master_filtered.empty or all_players_prev_seasons.empty:
        print("Data loading failed. Exiting.")
        return

    # Merge master with previous seasons' data
    merged_df = pd.merge(
        master_filtered,
        all_players_prev_seasons,
        left_on="fbref",
        right_on="Fbref",
        how="left",
    )
    merged_df = merged_df.drop(columns=["Fbref"])

    # Get FPL data
    fpl_elements = get_fpl_data()
    if fpl_elements.empty:
        print("FPL data retrieval failed. Exiting.")
        return

    # Merge with FPL data
    fpl_players = merged_df.merge(fpl_elements, on="fpl_id", how="inner")

    # Reorder columns
    fpl_players = fpl_players[
        [
            "fbref",
            "fpl_id",
            "first_name",
            "second_name",
            "Player",
            "web_name",
            "Age",
            "team_id",
            "team_name",
            "short_name",
            "element_type",
            "position",
            "Seasons_count",
            "now_cost",
            "tsb",
            "MP",
            "Starts",
            "Min",
            "90s",
            "npxG",
            "xAG",
            "finishing",
        ]
    ]

    # Get new season stats
    new_season = get_player_stats_new_season(
        "https://fbref.com/en/comps/9/stats/Premier-League-Stats"
    )
    if new_season.empty:
        print("New season data retrieval failed. Exiting.")
        return

    # Merge with new season stats
    new_season = new_season[["fbref", "MP", "90s", "npxG", "xAG"]]
    fpl_players_new_season = fpl_players.merge(
        new_season, on="fbref", how="left", suffixes=("", "_new")
    )

    # Calculate weighted stats
    calculate_weighted_stats(fpl_players_new_season, weight_new_data)

    fpl_players_new_season.drop_duplicates(subset="fpl_id", keep="first", inplace=True)

    players_not_found = fpl_players_new_season[fpl_players_new_season["Player"].isna()]

    if not players_not_found.empty:
        print("Top 20 players not found by tsb:")
        print_df = players_not_found[["fpl_id", "web_name", "tsb"]]
        print(print_df.sort_values(by="tsb", ascending=False).head(20))

    players_not_found.to_csv(
        "C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/players_not_found.csv",
        index=False,
    )

    fpl_players_new_season = fpl_players_new_season.dropna(subset=["Player"])

    max_mp = new_season["MP"].max()
    filename = f"fpl_players_new_season_gw{max_mp}.csv"

    # Save the final dataframe to a CSV or other format if needed
    fpl_players_new_season.to_csv(
        f"C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/{filename}",
        index=False,
    )
    print(f"Data processing complete. Output saved to {filename}")


if __name__ == "__main__":
    main()
