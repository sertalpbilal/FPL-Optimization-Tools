from tqdm import tqdm
import requests
import pandas as pd
import os
from bs4 import BeautifulSoup
import time
from io import StringIO
import re


def create_match_logs():
    try:
        fpl_players_path = f"C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/fpl_players_new_season.csv"

        # Check if files exist
        if not (os.path.exists(fpl_players_path)):
            raise FileNotFoundError(f"One or more necessary files do not.")

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

        seasons = ["2023-2024"]

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

        fpl_players_match_logs = pd.concat(all_dfs)
        fpl_players_match_logs = fpl_players_match_logs.merge(
            fpl_players[["fbref", "fpl_id", "Player", "weighted_npxGI"]],
            on="fbref",
            how="inner",
        )

        fpl_players_match_logs["Min"] = fpl_players_match_logs["Min"].apply(
            lambda x: 0 if x == "On matchday squad, but did not play" else x
        )
        fpl_players_match_logs["Pos"] = fpl_players_match_logs["Pos"].apply(
            lambda x: "Benched" if x == "On matchday squad, but did not play" else x
        )
        fpl_players_match_logs["Min"] = fpl_players_match_logs["Min"].astype(int)

        fpl_players_match_logs = fpl_players_match_logs[
            fpl_players_match_logs["Comp"].isin(
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

        fpl_players_match_logs.to_csv(
            "C:/Users/erknud3/fpl-optimization/model/data/Historic_Data/match_logs_prev_seasons.csv",
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
    create_match_logs()
