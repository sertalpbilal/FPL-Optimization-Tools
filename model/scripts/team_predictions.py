import sqlite3
import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests


def calculate_predictions(team_baselines):
    print("Calculating predictions for npxG and npxGC...")

    r = requests.get("https://fantasy.premierleague.com/api/fixtures/")
    fixtures = pd.DataFrame(r.json())
    fixtures = fixtures[["event", "team_h", "team_a"]]

    avg_npxG = team_baselines["npxG_baseline"].mean()
    avg_npxGC = team_baselines["npxGC_baseline"].mean()

    # Step 1: Calculate and Round Attack and Defense Multipliers
    team_baselines["attack_multiplier"] = np.round(
        (team_baselines["npxG_baseline"] / avg_npxG), 2
    )
    team_baselines["defense_multiplier"] = np.round(
        (team_baselines["npxGC_baseline"] / avg_npxGC), 2
    )

    npxG_pred = team_baselines[
        ["team_id", "team", "npxG_baseline", "attack_multiplier"]
    ].copy()
    npxGC_pred = team_baselines[
        ["team_id", "team", "npxGC_baseline", "defense_multiplier"]
    ].copy()

    # Step 3: Initialize New Columns
    for gw in range(1, 39):
        npxG_pred.loc[:, gw] = 0.0
        npxGC_pred.loc[:, gw] = 0.0

    # Step 4: Process Fixtures and Populate Gameweek Columns
    for index, row in fixtures.iterrows():
        gw = row["event"]
        team_h = row["team_h"]
        team_a = row["team_a"]

        # Get attack and defense multipliers
        home_attack = npxG_pred.loc[
            npxG_pred["team_id"] == team_h, "attack_multiplier"
        ].values[0]
        away_attack = npxG_pred.loc[
            npxG_pred["team_id"] == team_a, "attack_multiplier"
        ].values[0]
        home_defense = npxGC_pred.loc[
            npxGC_pred["team_id"] == team_h, "defense_multiplier"
        ].values[0]
        away_defense = npxGC_pred.loc[
            npxGC_pred["team_id"] == team_a, "defense_multiplier"
        ].values[0]

        # Get baseline npxG and npxGC
        home_npxG = npxG_pred.loc[
            npxG_pred["team_id"] == team_h, "npxG_baseline"
        ].values[0]
        away_npxG = npxG_pred.loc[
            npxG_pred["team_id"] == team_a, "npxG_baseline"
        ].values[0]
        home_npxGC = npxGC_pred.loc[
            npxGC_pred["team_id"] == team_h, "npxGC_baseline"
        ].values[0]
        away_npxGC = npxGC_pred.loc[
            npxGC_pred["team_id"] == team_a, "npxGC_baseline"
        ].values[0]

        # Adjust for home/away and opponent strength, then round to 2 decimals
        npxG_pred.loc[npxG_pred["team_id"] == team_h, gw] = round(
            home_npxG * away_defense * 1.12, 2
        )
        npxG_pred.loc[npxG_pred["team_id"] == team_a, gw] = round(
            away_npxG * home_defense * 0.88, 2
        )

        npxGC_pred.loc[npxGC_pred["team_id"] == team_h, gw] = round(
            home_npxGC * away_attack * 0.88, 2
        )
        npxGC_pred.loc[npxGC_pred["team_id"] == team_a, gw] = round(
            away_npxGC * home_attack * 1.12, 2
        )

    # Step 5: Drop the attack_multiplier and defense_multiplier columns
    npxG_pred.drop(columns=["attack_multiplier"], inplace=True)
    npxGC_pred.drop(columns=["defense_multiplier"], inplace=True)

    attack_multipliers = npxG_pred.copy()

    for gw in range(1, 39):
        attack_multipliers[gw] = np.round(
            (attack_multipliers[gw] / attack_multipliers["npxG_baseline"]), 2
        )

    return npxG_pred, npxGC_pred, attack_multipliers


def calculate_gc_probabilities(npxGC_pred):
    print("Calculating Goal Conceded Probabilities...")

    # Step 1: Initialize an empty DataFrame to store the probabilities
    columns = ["team_id", "Squad"] + [
        f"{gw}_{goals}_goals" for gw in range(1, 39) for goals in range(9)
    ]
    team_concede_probs = pd.DataFrame(columns=columns)

    # Step 2: Calculate probabilities for each team and gameweek
    for idx, row in npxGC_pred.iterrows():
        team_id = row["team_id"]
        team = row["team"]

        probabilities = []

        for gw in range(1, 39):
            mean_goals_conceded = row[gw]
            probs = poisson.pmf(range(9), mean_goals_conceded).round(4)
            probabilities.extend(probs)

        # Insert the data into the new DataFrame
        team_concede_probs.loc[idx] = [team_id, team] + list(probabilities)

    # Initialize a new DataFrame to store the cumulative probabilities
    gc_probabilities = pd.DataFrame(
        columns=["team_id", "Squad"]
        + [
            f"{gw}_{concede}_goals"
            for gw in range(1, 39)
            for concede in [0, 1, 2, 4, 6, 8]
        ]
    )

    # Calculate cumulative probabilities for each team and gameweek
    for idx, row in team_concede_probs.iterrows():
        team_id = row["team_id"]
        squad = row["Squad"]

        cum_probs = []

        for gw in range(1, 39):
            prob_0 = row[f"{gw}_0_goals"]
            prob_1 = row[f"{gw}_1_goals"]
            prob_2 = row[f"{gw}_2_goals"]
            prob_4 = row[f"{gw}_4_goals"]
            prob_6 = row[f"{gw}_6_goals"]
            prob_8_or_more = row[f"{gw}_8_goals"] + sum(
                row[f"{gw}_{k}_goals"] for k in range(9, len(row) // 38)
            )

            cum_probs.extend([prob_0, prob_1, prob_2, prob_4, prob_6, prob_8_or_more])

        # Insert the data into the new DataFrame
        gc_probabilities.loc[idx] = [team_id, squad] + cum_probs

    return gc_probabilities


def main():
    # Connect to the SQLite database
    conn = sqlite3.connect("C:/Users/erknud3/fpl-optimization/model/FBRef_DB/master.db")

    print("Loading data from the database...")

    # Load data from Match table
    team_baselines = pd.read_sql_query(
        """
        SELECT team_id, team, npxG_baseline, npxGC_baseline
        FROM team_baselines
        """,
        conn,
    )

    # Close the connection
    # conn.close()

    npxG_pred, npxGC_pred, attack_multipliers = calculate_predictions(team_baselines)
    gc_probabilities = calculate_gc_probabilities(npxGC_pred)

    # Define table names for the DataFrames
    tables = {
        "npxG_pred": npxG_pred,
        "npxGC_pred": npxGC_pred,
        "attack_multipliers": attack_multipliers,
        "gc_probabilities": gc_probabilities,
    }

    cursor = conn.cursor()

    for table_name, table_data in tables.items():
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
            table_data.to_sql(table_name, conn, if_exists="append", index=False)
            print(f"Data inserted into table '{table_name}'.")
        else:
            # If the table does not exist, create it and insert data
            print(
                f"Table '{table_name}' not found. Creating table and inserting data..."
            )
            table_data.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"Table '{table_name}' created and data inserted.")

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
