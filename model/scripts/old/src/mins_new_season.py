from tqdm import tqdm
import requests
import pandas as pd
import os
from bs4 import BeautifulSoup
import time
from io import StringIO
import re


def calculate_xmins():
    try:
        fpl_players_path = f"C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/fpl_players_new_season.csv"

        # Check if files exist
        if not (os.path.exists(fpl_players_path)):
            raise FileNotFoundError(f"One or more necessary files do not exist.")

        fpl_players = pd.read_csv(fpl_players_path)

        fpl_players = fpl_players[
            ["fbref", "fpl_id", "Player", "weighted_npxG", "weighted_xAG"]
        ]

        fpl_players["weighted_npxGI"] = (
            fpl_players["weighted_npxG"] + fpl_players["weighted_xAG"]
        )

        fpl_players.dropna(subset=["weighted_npxGI"], inplace=True)

        fpl_players = fpl_players.sort_values(by="weighted_npxGI", ascending=False)

        # Initialize an empty list to store the URLs
        player_urls = []

        # Loop through each row in the DataFrame
        for index, row in fpl_players.iterrows():
            fbref_id = row["fbref"]
            player_name = row["Player"]
            player_name_url = player_name.replace(" ", "-")
            url = f"https://fbref.com/en/players/{fbref_id}/{player_name_url}"
            player_urls.append(url)

        seasons = ["2024-2025"]

        # Function to construct season links from player URL
        def construct_season_links(player_url, seasons):
            # Extract the base part of the URL, player ID, and player name
            base_url = player_url.split("/players/")[0]
            fbref_id = player_url.split("/players/")[1].split("/")[0]
            player_name = player_url.split("/")[-1]

            # Construct the season URLs and return them as a single list
            return [
                f"{base_url}/players/{fbref_id}/matchlogs/{season}/summary/{player_name}-Match-Logs"
                for season in seasons
            ]

        # Loop through each player URL and construct the season URLs, flattening the results directly
        all_season_links = []
        for url in player_urls:
            season_links = construct_season_links(url, seasons)
            all_season_links.extend(season_links)

        all_dfs = []

        # Initialize the progress bar
        with tqdm(total=len(all_season_links), desc="Processing URLs") as pbar:
            for url in all_season_links:
                try:
                    data = requests.get(url)
                    soup = BeautifulSoup(data.text, "html.parser")
                    ids = re.search(r"/players/([a-zA-Z0-9]{8})/", url)
                    season = re.search(r"/(\d{4}-\d{4})/", url)

                    table = soup.find("table", {"id": "matchlogs_all"})

                    df = pd.read_html(StringIO(str(table)))[0]
                    df.columns = [
                        f"{i} {j}" if "Unnamed" not in i else j for i, j in df.columns
                    ]
                    df = df[
                        [
                            "Date",
                            "Day",
                            "Comp",
                            "Round",
                            "Venue",
                            "Result",
                            "Squad",
                            "Opponent",
                            "Start",
                            "Pos",
                            "Min",
                        ]
                    ]

                    # Add fbref ID and season columns
                    df["fbref"] = ids.group(1)
                    df["Season"] = season.group(1)
                    cols_to_move = ["fbref", "Season"]
                    remaining_cols = [
                        col for col in df.columns if col not in cols_to_move
                    ]
                    new_order = remaining_cols[:1] + cols_to_move + remaining_cols[1:]

                    df = df[new_order]
                    df.dropna(inplace=True)
                    # df = df[df['Comp'] == "Premier League"]

                    # Append the DataFrame to the list
                    all_dfs.append(df)

                    # Sleep to avoid overloading the server
                    time.sleep(12)

                except Exception as e:
                    print(f"An error occurred for URL: {url}: {e}")

                # Update the progress bar
                pbar.update(1)

        match_logs_new_season = pd.concat(all_dfs)
        match_logs_new_season = match_logs_new_season.merge(
            fpl_players[["fbref", "fpl_id", "Player", "weighted_npxGI"]],
            on="fbref",
            how="inner",
        )

        match_logs_new_season["Min"] = match_logs_new_season["Min"].apply(
            lambda x: 0 if x == "On matchday squad, but did not play" else x
        )
        match_logs_new_season["Pos"] = match_logs_new_season["Pos"].apply(
            lambda x: "Benched" if x == "On matchday squad, but did not play" else x
        )
        match_logs_new_season["Min"] = match_logs_new_season["Min"].astype(int)

        match_logs_new_season = match_logs_new_season[
            match_logs_new_season["Comp"].isin(
                [
                    "Premier League",
                    "Bundesliga",
                    "La Liga",
                    "Serie A",
                    "Ligue 1",
                    "Primeira Liga",
                    "Championship",
                    "Eredivisie",
                ]
            )
        ]

        match_logs_new_season.to_csv(
            "C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/match_logs_new_season.csv",
            index=False,
        )

        match_logs_prev_seaons = pd.read_csv(
            "C:/Users/erknud3/fpl-optimization/model/data/Historic_Data/match_logs_prev_seasons.csv"
        )

        match_logs = pd.concat([match_logs_new_season, match_logs_prev_seaons])

        # Convert 'Date' to datetime and sort the data
        match_logs["Date"] = pd.to_datetime(match_logs["Date"])
        match_logs.sort_values(by=["fbref", "Date"], inplace=True)

        # Feature Engineering
        match_logs["Start_Flag"] = match_logs["Start"].apply(
            lambda x: 1 if x in ["Y", "Y*"] else 0
        )
        match_logs["Play_1_Min"] = match_logs["Min"].apply(lambda x: 1 if x > 0 else 0)
        match_logs["Play_60_Min"] = match_logs["Min"].apply(
            lambda x: 1 if x >= 60 else 0
        )

        # Assume match_logs is already sorted and contains the data
        # Create a flag for squad changes
        match_logs["Squad_Change"] = match_logs.groupby("fbref")["Squad"].transform(
            lambda x: x != x.shift()
        )

        # Calculate long-term trend based on the previous season
        match_logs["Previous_Season_Minutes"] = (
            match_logs.groupby(["fbref", "Season"])["Min"]
            .transform(lambda x: x.shift(1).expanding().mean())
            .round(2)
        )
        match_logs["Previous_Season_Minutes"] = match_logs[
            "Previous_Season_Minutes"
        ].ffill()

        # Weight the long-term trend less if there's a squad change
        match_logs["Baseline_Minutes"] = match_logs["Previous_Season_Minutes"]
        match_logs.loc[match_logs["Squad_Change"], "Baseline_Minutes"] *= 0.5

        # Calculate EMA for the current season
        match_logs["Current_Season_Minutes_EMA"] = (
            match_logs.groupby(["fbref", "Season"])["Min"]
            .transform(lambda x: x.ewm(span=6).mean())
            .round(2)
        )

        # Combine the baseline and current season EMA to get the expected minutes
        match_logs["Expected_Minutes"] = (
            match_logs["Baseline_Minutes"] * 0.3
            + match_logs["Current_Season_Minutes_EMA"] * 0.7
        ).round(2)

        # Optional: Clip values to avoid extreme outliers
        match_logs["Expected_Minutes"] = match_logs["Expected_Minutes"].clip(
            lower=0, upper=90
        )

        # Calculate long-term trends for start, play at least 1 minute, and play at least 60 minutes

        # P(start) - Long-term trend based on the previous season
        match_logs["Previous_Season_P(start)"] = (
            match_logs.groupby(["fbref", "Season"])["Start_Flag"]
            .transform(lambda x: x.shift(1).expanding().mean())
            .round(2)
        )
        match_logs["Previous_Season_P(start)"] = match_logs[
            "Previous_Season_P(start)"
        ].ffill()

        # P(play_1_min) - Long-term trend based on the previous season
        match_logs["Previous_Season_P(play_1_min)"] = (
            match_logs.groupby(["fbref", "Season"])["Play_1_Min"]
            .transform(lambda x: x.shift(1).expanding().mean())
            .round(2)
        )
        match_logs["Previous_Season_P(play_1_min)"] = match_logs[
            "Previous_Season_P(play_1_min)"
        ].ffill()

        # P(play_60_min) - Long-term trend based on the previous season
        match_logs["Previous_Season_P(play_60_min)"] = (
            match_logs.groupby(["fbref", "Season"])["Play_60_Min"]
            .transform(lambda x: x.shift(1).expanding().mean())
            .round(2)
        )
        match_logs["Previous_Season_P(play_60_min)"] = match_logs[
            "Previous_Season_P(play_60_min)"
        ].ffill()

        # Weight the long-term trends less if there's a squad change
        match_logs["Baseline_P(start)"] = match_logs["Previous_Season_P(start)"]
        match_logs["Baseline_P(play_1_min)"] = match_logs[
            "Previous_Season_P(play_1_min)"
        ]
        match_logs["Baseline_P(play_60_min)"] = match_logs[
            "Previous_Season_P(play_60_min)"
        ]

        match_logs.loc[match_logs["Squad_Change"], "Baseline_P(start)"] *= 0.5
        match_logs.loc[match_logs["Squad_Change"], "Baseline_P(play_1_min)"] *= 0.5
        match_logs.loc[match_logs["Squad_Change"], "Baseline_P(play_60_min)"] *= 0.5

        # Calculate EMA for the current season for each probability
        match_logs["Current_Season_P(start)_EMA"] = (
            match_logs.groupby(["fbref", "Season"])["Start_Flag"]
            .transform(lambda x: x.ewm(span=6).mean())
            .round(2)
        )
        match_logs["Current_Season_P(play_1_min)_EMA"] = (
            match_logs.groupby(["fbref", "Season"])["Play_1_Min"]
            .transform(lambda x: x.ewm(span=6).mean())
            .round(2)
        )
        match_logs["Current_Season_P(play_60_min)_EMA"] = (
            match_logs.groupby(["fbref", "Season"])["Play_60_Min"]
            .transform(lambda x: x.ewm(span=6).mean())
            .round(2)
        )

        # Combine the baseline and current season EMA to get the final probabilities
        match_logs["P(start)"] = (
            match_logs["Baseline_P(start)"] * 0.3
            + match_logs["Current_Season_P(start)_EMA"] * 0.7
        ).round(2)
        match_logs["P(play_1_min)"] = (
            match_logs["Baseline_P(play_1_min)"] * 0.3
            + match_logs["Current_Season_P(play_1_min)_EMA"] * 0.7
        ).round(2)
        match_logs["P(play_60_min)"] = (
            match_logs["Baseline_P(play_60_min)"] * 0.3
            + match_logs["Current_Season_P(play_60_min)_EMA"] * 0.7
        ).round(2)

        match_logs = match_logs[
            [
                "Date",
                "fbref",
                "fpl_id",
                "Player",
                "weighted_npxGI",
                "Season",
                "Comp",
                "Round",
                "Squad",
                "Opponent",
                "Min",
                "Start_Flag",
                "Expected_Minutes",
                "P(start)",
                "P(play_1_min)",
                "P(play_60_min)",
            ]
        ]

        # Ensure the data is sorted by 'fbref' and 'Date' so the most recent rows are at the end
        match_logs.sort_values(by=["fbref", "Date"], inplace=True)

        match_logs.to_csv(
            "C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/match_logs.csv",
            index=False,
        )

        # Drop duplicates, keeping only the last entry (which is the most recent) for each player ('fbref')
        fpl_players_xmins = match_logs.drop_duplicates(subset=["fbref"], keep="last")

        # Reset the index for the new dataframe (optional, for cleaner presentation)
        fpl_players_xmins.reset_index(drop=True, inplace=True)

        fpl_players_xmins = fpl_players_xmins[
            [
                "Date",
                "fbref",
                "fpl_id",
                "Player",
                "Season",
                "Comp",
                "Round",
                "Squad",
                "Min",
                "Start_Flag",
                "Expected_Minutes",
                "P(start)",
                "P(play_1_min)",
                "P(play_60_min)",
                "weighted_npxGI",
            ]
        ]

        fpl_players_xmins = fpl_players_xmins.rename(
            {
                "Min": "Mins",
                "Start_Flag": "Start",
                "Expected_Minutes": "xMins",
                "P(play_1_min)": "P(1_min)",
                "P(play_60_min)": "P(60_min)",
            },
            axis=1,
        )

        fpl_players_xmins = fpl_players_xmins.sort_values(
            by="weighted_npxGI", ascending=False
        )

        fpl_players_xmins.to_csv(
            "C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/fpl_players_xmins.csv",
            index=False,
        )

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except KeyError as e:
        print(f"Key error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    # newest_gw = input("Enter the newest gameweek number: ")
    calculate_xmins()
