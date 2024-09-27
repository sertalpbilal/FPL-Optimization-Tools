import sqlite3
import pandas as pd
import numpy as np


def create_player_dfs(player_info):
    player_stats = player_info.copy()
    player_minutes = player_info[
        [
            "match_id",
            "player_id",
            "fpl_id",
            "name",
            "web_name",
            "competition",
            "season",
            "team",
            "opponent",
            "date",
            "started_match",
            "minutes",
        ]
    ].copy()

    player_stats = (
        player_info.groupby(
            ["player_id", "fpl_id", "name", "web_name", "competition", "season", "team"]
        )
        .agg(
            games=("match_id", "count"),
            last_date=("date", "max"),
            minutes=("minutes", "sum"),
            npxG=("npxG", "sum"),
            xA=("xA", "sum"),
        )
        .reset_index()
    )

    skill_and_cards = (
        player_info.groupby(["player_id", "fpl_id", "name", "web_name"])
        .agg(
            games=("match_id", "count"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            penalties_scored=("penalties_scored", "sum"),
            penalties_attempted=("penalties_attempted", "sum"),
            npxG=("npxG", "sum"),
            xA=("xA", "sum"),
            yellow_cards=("yellow_cards", "sum"),
            red_cards=("red_cards", "sum"),
        )
        .reset_index()
    )

    penalties = (
        player_info.groupby(
            ["player_id", "fpl_id", "name", "web_name", "competition", "season", "team"]
        )
        .agg(
            games=("match_id", "count"),
            penalties_scored=("penalties_scored", "sum"),
            penalties_attempted=("penalties_attempted", "sum"),
        )
        .reset_index()
    )

    player_stats["ninetys"] = np.round(player_stats["minutes"] / 90, 2)
    player_stats["npxG"] = np.round(
        (player_stats["npxG"]) / (player_stats["ninetys"]), 2
    )
    player_stats["xA"] = np.round((player_stats["xA"]) / (player_stats["ninetys"]), 2)
    player_stats = player_stats.rename({"ninetys": "90s"}, axis=1)
    player_stats = player_stats[
        [
            "player_id",
            "fpl_id",
            "name",
            "web_name",
            "competition",
            "season",
            "team",
            "games",
            "last_date",
            "minutes",
            "90s",
            "npxG",
            "xA",
        ]
    ]

    skill_and_cards["finishing_skill"] = np.round(
        (skill_and_cards["goals"] - skill_and_cards["penalties_scored"] + 55)
        / (skill_and_cards["npxG"] + 55),
        2,
    )
    skill_and_cards["assist_skill"] = np.round(
        (skill_and_cards["assists"] + 55) / (skill_and_cards["xA"] + 55), 2
    )
    skill_and_cards["pen_skill"] = np.where(
        skill_and_cards["penalties_attempted"] < 15,
        1,
        np.round(
            (
                skill_and_cards["penalties_scored"]
                / skill_and_cards["penalties_attempted"]
            )
            / 0.77,
            2,
        ),
    )
    skill_and_cards["prob_yellow"] = np.round(
        skill_and_cards["yellow_cards"] / skill_and_cards["games"], 2
    )
    skill_and_cards["prob_red"] = np.round(
        skill_and_cards["red_cards"] / skill_and_cards["games"], 2
    )

    penalties = penalties[penalties["penalties_attempted"] > 0]

    return player_stats, player_minutes, skill_and_cards, penalties


def calculate_prior_and_new(player_df, is_previous=True):

    multipliers = {
        "Premier_League": 1,
        "Ligue_1": 0.75,
        "Serie_A": 0.75,
        "Bundesliga": 0.75,
        "La_Liga": 0.75,
        "Primeira_Liga": 0.5,
        "Championship": 0.5,
        "Eredivisie": 0.5,
    }

    # Filter previous seasons (prior to 2024-2025) or current season
    if is_previous:
        player_df = player_df[player_df["season"] != "2024-2025"].copy()
    else:
        player_df = player_df[
            (player_df["season"] == "2024-2025")
            & (player_df["competition"] == "Premier_League")
        ].copy()

    # If there are no previous seasons or current season data, return NaNs
    if player_df.empty:
        columns = [
            "npxG",
            "xA",
            "90s",
        ]
        if is_previous:
            return pd.Series({f"prior_{col}": np.nan for col in columns})
        else:
            return pd.Series({f"{col}": np.nan for col in columns})

    # Apply competition multipliers
    player_df["comp_multiplier"] = player_df["competition"].map(multipliers)

    # Compute season weights based on recency (latest season gets highest weight)
    if is_previous:
        player_df = player_df.sort_values(by="season", ascending=False)
        player_df["season_weight"] = np.arange(len(player_df), 0, -1)
    else:
        player_df = player_df.sort_values(by="season", ascending=False)
        player_df["season_weight"] = 1

    # Calculate weighted stats for prior beliefs and new evidence
    weighted_columns = ["npxG", "xA"]
    for col in weighted_columns:
        if is_previous:
            player_df[f"weighted_{col}"] = (
                player_df[col]
                * player_df["comp_multiplier"]
                * player_df["90s"]
                * player_df["season_weight"]
            )
        else:
            player_df[f"weighted_{col}"] = (
                player_df[col] * player_df["90s"] * player_df["season_weight"]
            )

    # Calculate weighted stats for non-comp-multiplied columns
    non_weighted_columns = [
        "90s",
    ]
    for col in non_weighted_columns:
        player_df[f"weighted_{col}"] = (
            player_df[col] * player_df["90s"] * player_df["season_weight"]
        )

    # Calculate total weights for normalization
    total_weight = (player_df["90s"] * player_df["season_weight"]).sum()

    # Compute prior beliefs or new evidence as weighted averages
    result = {}
    for col in weighted_columns:
        if is_previous:
            result[f"prior_{col}"] = np.round(
                (
                    player_df[f"weighted_{col}"].sum() / total_weight
                    if total_weight > 0
                    else np.nan
                ),
                2,
            )
        else:
            result[f"{col}"] = np.round(
                (
                    player_df[f"weighted_{col}"].sum() / total_weight
                    if total_weight > 0
                    else np.nan
                ),
                2,
            )

    # Compute non-weighted column averages
    for col in non_weighted_columns:
        if is_previous:
            result[f"prior_{col}"] = np.round(
                (
                    player_df[f"weighted_{col}"].sum() / total_weight
                    if total_weight > 0
                    else np.nan
                ),
                2,
            )
        else:
            result[f"{col}"] = np.round(
                (
                    player_df[f"weighted_{col}"].sum() / total_weight
                    if total_weight > 0
                    else np.nan
                ),
                2,
            )

    return pd.Series(result)


def merge_prior_and_new_evidence(player_stats):
    # Step 1: Apply the function to each player and store the results in separate lists
    player_prior_beliefs_list = []
    player_new_evidence_list = []

    # Iterate over unique player_ids and compute prior beliefs and new evidence for each player
    for player_id, group in player_stats.groupby("player_id"):
        # Compute prior beliefs
        prior_beliefs = calculate_prior_and_new(group, is_previous=True)
        if isinstance(prior_beliefs, pd.Series):
            prior_beliefs = prior_beliefs.to_frame().T
        prior_beliefs["player_id"] = player_id
        player_prior_beliefs_list.append(prior_beliefs)

        # Compute new evidence
        new_evidence = calculate_prior_and_new(group, is_previous=False)
        if isinstance(new_evidence, pd.Series):
            new_evidence = new_evidence.to_frame().T
        new_evidence["player_id"] = player_id
        player_new_evidence_list.append(new_evidence)

    # Concatenate all the prior beliefs and new evidence into separate DataFrames
    player_prior_beliefs_df = pd.concat(player_prior_beliefs_list, ignore_index=True)
    player_new_evidence_df = pd.concat(player_new_evidence_list, ignore_index=True)

    # Step 2: Extract the relevant columns for the current season (2024-2025)
    current_season_df = player_stats[
        (player_stats["season"] == "2024-2025")
        & (player_stats["competition"] == "Premier_League")
    ][
        [
            "player_id",
            "fpl_id",
            "name",
            "web_name",
            "competition",
            "season",
            "team",
            "games",
            "last_date",
            "minutes",
            "90s",
        ]
    ]

    # Step 3: Combine prior beliefs with the current season data
    final_df_prior = pd.merge(
        current_season_df, player_prior_beliefs_df, on="player_id", how="left"
    )
    final_df = pd.merge(
        final_df_prior, player_new_evidence_df, on="player_id", how="left"
    )

    # final_df = final_df.drop(columns=['90s_y'])
    final_df = final_df.rename(columns={"90s_x": "90s"})
    final_df = final_df[
        [
            "player_id",
            "fpl_id",
            "name",
            "web_name",
            "competition",
            "season",
            "team",
            "games",
            "last_date",
            "minutes",
            "90s",
            "npxG",
            "xA",
            "prior_90s",
            "prior_npxG",
            "prior_xA",
        ]
    ]

    return final_df


def calculate_baselines(final_df):
    # Columns for which we need to calculate baselines
    stat_columns = [
        "npxG",
        "xA",
    ]

    # Calculate total 90s (current + prior)
    total_90s = final_df["90s"] + final_df["prior_90s"]

    # Initialize a dictionary to hold the baseline calculations
    baseline_data = {}

    # Calculate baselines for each stat column
    for col in stat_columns:
        baseline_data[f"{col}_baseline"] = (
            final_df[col] * final_df["90s"]
            + final_df[f"prior_{col}"] * final_df["prior_90s"]
        ) / total_90s

    # Add baseline columns to the DataFrame
    for key, values in baseline_data.items():
        final_df[key] = values

    # Round the results to 2 decimal places
    baseline_columns = [f"{col}_baseline" for col in stat_columns]
    final_df[baseline_columns] = final_df[baseline_columns].round(2)
    prior_columns = [f"prior_{col}" for col in stat_columns]
    final_df[prior_columns] = final_df[prior_columns].round(2)

    # Create a new DataFrame with the baselines
    player_baselines = final_df[
        [
            "player_id",
            "fpl_id",
            "name",
            "web_name",
            "competition",
            "season",
            "team",
            "games",
            "last_date",
            "minutes",
            "90s",
            "npxG",
            "xA",
        ]
        + baseline_columns
        + prior_columns
    ]

    player_baselines = player_baselines.sort_values("last_date").drop_duplicates(
        subset=["player_id", "fpl_id", "name", "web_name", "competition", "season"],
        keep="last",
    )

    player_baselines = player_baselines.drop(columns="last_date")

    return player_baselines


def main():
    # Connect to the SQLite database
    conn = sqlite3.connect("C:/Users/erknud3/fpl-optimization/model/FBRef_DB/master.db")

    print("Loading data from the database...")

    # Load data from Match table
    player_info = pd.read_sql_query(
        """
        select a.match_id, a.player_id, "24-25" fpl_id, name, web_name, competition, season, date, home_team, away_team, home_away, started_match, age, minutes, goals, assists, penalties_scored, penalties_attempted,
        yellow_cards, red_cards, npxG, xA
        from Player_Info a
        join fpl_master_24_25 b on a.player_id = b.fbref
        join Summary c on a.player_id = c.player_id and a.match_id = c.match_id
        join Match d on a.match_id = d.match_id
        """,
        conn,
    )

    # # Close the connection
    # conn.close()

    # Calculate 'team' and 'opponent' columns
    player_info["team"] = player_info.apply(
        lambda row: row["home_team"] if row["home_away"] == "H" else row["away_team"],
        axis=1,
    )
    player_info["opponent"] = player_info.apply(
        lambda row: row["away_team"] if row["home_away"] == "H" else row["home_team"],
        axis=1,
    )

    player_info = player_info.drop(["home_team", "away_team", "home_away"], axis=1)

    print("Creating dataframes...")
    player_stats, player_minutes, skill_and_cards, penalties = create_player_dfs(
        player_info
    )

    print("Merging prior and new evidence...")
    final_df = merge_prior_and_new_evidence(player_stats)

    print("Calculating baselines...")
    player_baselines = calculate_baselines(final_df)

    cursor = conn.cursor()

    # Table name
    player_baselines_table = "player_baselines"
    player_minutes_table = "player_minutes"
    skill_and_cards_table = "skill_and_cards"
    penalties_table = "penalties"

    # Function to handle table creation and data insertion
    def create_or_replace_table(table_name, dataframe, cursor, conn):
        # Check if the table exists
        cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';"
        )
        table_exists = cursor.fetchone()

        if table_exists:
            # If the table exists, truncate (delete all rows)
            cursor.execute(f"DELETE FROM {table_name};")
            print(f"Table '{table_name}' found. Truncating table...")

            # Insert data into the table
            dataframe.to_sql(table_name, conn, if_exists="append", index=False)
            print(f"Data inserted into table '{table_name}'.")
        else:
            # If the table does not exist, create it and insert data
            print(
                f"Table '{table_name}' not found. Creating table and inserting data..."
            )
            dataframe.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"Table '{table_name}' created and data inserted.")

    # Create or replace tables for player_baselines and player_minutes
    create_or_replace_table(player_baselines_table, player_baselines, cursor, conn)
    create_or_replace_table(player_minutes_table, player_minutes, cursor, conn)
    create_or_replace_table(skill_and_cards_table, skill_and_cards, cursor, conn)
    create_or_replace_table(penalties_table, penalties, cursor, conn)

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
