import pandas as pd
import requests
from scipy.stats import poisson


def load_team_data(filepath_for, filepath_against):
    team_stats_new_season_for = pd.read_csv(filepath_for)
    team_stats_new_season_against = pd.read_csv(filepath_against)

    team_stats_new_season_for = team_stats_new_season_for[
        ["team_id", "Squad", "90s_new", "weighted_npxG"]
    ]
    team_stats_new_season_against = team_stats_new_season_against[
        ["team_id", "Squad", "90s_new", "weighted_npxGC"]
    ]

    r = requests.get("https://fantasy.premierleague.com/api/fixtures/")
    fixtures = pd.DataFrame(r.json())
    fixtures = fixtures[["event", "team_h", "team_a"]]

    avg_npxG = team_stats_new_season_for["weighted_npxG"].mean()
    avg_npxGC = team_stats_new_season_against["weighted_npxGC"].mean()

    # Step 1: Calculate and Round Attack and Defense Multipliers
    team_stats_new_season_for["attack_multiplier"] = (
        team_stats_new_season_for["weighted_npxG"] / avg_npxG
    ).round(2)
    team_stats_new_season_against["defense_multiplier"] = (
        team_stats_new_season_against["weighted_npxGC"] / avg_npxGC
    ).round(2)

    # Step 2: Rename weighted_npxG and weighted_npxGC
    team_stats_new_season_for.rename(
        columns={"weighted_npxG": "baseline_npxG"}, inplace=True
    )
    team_stats_new_season_against.rename(
        columns={"weighted_npxGC": "baseline_npxGC"}, inplace=True
    )

    # Step 3: Initialize New Columns
    for gw in range(1, 39):
        team_stats_new_season_for[gw] = 0.0
        team_stats_new_season_against[gw] = 0.0

    # Step 4: Process Fixtures and Populate Gameweek Columns
    for index, row in fixtures.iterrows():
        gw = row["event"]
        team_h = row["team_h"]
        team_a = row["team_a"]

        # Get attack and defense multipliers
        home_attack = team_stats_new_season_for.loc[
            team_stats_new_season_for["team_id"] == team_h, "attack_multiplier"
        ].values[0]
        away_attack = team_stats_new_season_for.loc[
            team_stats_new_season_for["team_id"] == team_a, "attack_multiplier"
        ].values[0]
        home_defense = team_stats_new_season_against.loc[
            team_stats_new_season_against["team_id"] == team_h, "defense_multiplier"
        ].values[0]
        away_defense = team_stats_new_season_against.loc[
            team_stats_new_season_against["team_id"] == team_a, "defense_multiplier"
        ].values[0]

        # Get baseline npxG and npxGC
        home_npxG = team_stats_new_season_for.loc[
            team_stats_new_season_for["team_id"] == team_h, "baseline_npxG"
        ].values[0]
        away_npxG = team_stats_new_season_for.loc[
            team_stats_new_season_for["team_id"] == team_a, "baseline_npxG"
        ].values[0]
        home_npxGC = team_stats_new_season_against.loc[
            team_stats_new_season_against["team_id"] == team_h, "baseline_npxGC"
        ].values[0]
        away_npxGC = team_stats_new_season_against.loc[
            team_stats_new_season_against["team_id"] == team_a, "baseline_npxGC"
        ].values[0]

        # Adjust for home/away and opponent strength, then round to 2 decimals
        team_stats_new_season_for.loc[
            team_stats_new_season_for["team_id"] == team_h, gw
        ] = round(home_npxG * away_defense * 1.12, 2)
        team_stats_new_season_for.loc[
            team_stats_new_season_for["team_id"] == team_a, gw
        ] = round(away_npxG * home_defense * 0.88, 2)

        team_stats_new_season_against.loc[
            team_stats_new_season_against["team_id"] == team_h, gw
        ] = round(home_npxGC * away_attack * 0.88, 2)
        team_stats_new_season_against.loc[
            team_stats_new_season_against["team_id"] == team_a, gw
        ] = round(away_npxGC * home_attack * 1.12, 2)

    # Step 5: Drop the attack_multiplier and defense_multiplier columns
    team_stats_new_season_for.drop(columns=["attack_multiplier"], inplace=True)
    team_stats_new_season_against.drop(columns=["defense_multiplier"], inplace=True)

    # Step 6: Ensure all columns are rounded to 2 decimals
    team_stats_new_season_for = team_stats_new_season_for.round(2)
    team_stats_new_season_against = team_stats_new_season_against.round(2)

    for gw in range(1, 39):
        team_stats_new_season_for[gw] = (
            team_stats_new_season_for[gw] / team_stats_new_season_for["baseline_npxG"]
        ).round(2)

    return team_stats_new_season_for, team_stats_new_season_against


def main():
    filepath_for = "C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/teams_new_season_for.csv"
    filepath_against = "C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/teams_new_season_against.csv"
    save_file_path = "C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data"

    team_stats_new_season_for, team_stats_new_season_against = load_team_data(
        filepath_for, filepath_against
    )

    if not team_stats_new_season_for.empty:
        team_stats_new_season_for.to_csv(
            f"{save_file_path}/teams_pred_npxG.csv", index=False
        )
        print(f"'For' data successfully saved to teams_pred_npxG.csv")
    else:
        print("No 'for' data to save.")

    if not team_stats_new_season_against.empty:
        team_stats_new_season_against.to_csv(
            f"{save_file_path}/teams_pred_npxGC.csv", index=False
        )
        print(f"'Against' data successfully saved to teams_pred_npxGC.csv")
    else:
        print("No 'against' data to save.")

    # Step 1: Initialize an empty DataFrame to store the probabilities
    columns = ["team_id", "Squad"] + [
        f"{gw}_{goals}_goals" for gw in range(1, 39) for goals in range(9)
    ]
    team_concede_probs = pd.DataFrame(columns=columns)

    # Step 2: Calculate probabilities for each team and gameweek
    for idx, row in team_stats_new_season_against.iterrows():
        team_id = row["team_id"]
        squad = row["Squad"]

        probabilities = []

        for gw in range(1, 39):
            mean_goals_conceded = row[gw]
            probs = poisson.pmf(range(9), mean_goals_conceded).round(4)
            probabilities.extend(probs)

        # Insert the data into the new DataFrame
        team_concede_probs.loc[idx] = [team_id, squad] + list(probabilities)

    # Initialize a new DataFrame to store the cumulative probabilities
    GC_probabilities = pd.DataFrame(
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
        GC_probabilities.loc[idx] = [team_id, squad] + cum_probs

    gc_file_path = "C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data"
    if not GC_probabilities.empty:
        try:
            GC_probabilities.to_csv(f"{gc_file_path}/gc_probabilities.csv", index=False)
            print(f"Goals conceded data successfully saved to gc_probabilities.csv")
        except Exception as e:
            print(f"Error saving gc_probabilities.csv: {e}")
    else:
        print("No goals conceded data to save.")


if __name__ == "__main__":
    main()
