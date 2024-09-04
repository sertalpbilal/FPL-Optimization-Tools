import pandas as pd
import os


def calculate_player_ev(newest_gw):
    try:
        # Load the necessary CSV files
        fpl_players_path = f"C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/fpl_players_new_season_gw{newest_gw}.csv"
        teams_pred_npxG_path = f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/teams_pred_npxG_gw{newest_gw}.csv"
        gc_probs_path = f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/GC_probabilities.csv"
        pen_share_path = f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/pen_share.csv"

        # Check if files exist
        if not (
            os.path.exists(fpl_players_path)
            and os.path.exists(teams_pred_npxG_path)
            and os.path.exists(gc_probs_path)
        ):
            raise FileNotFoundError(
                f"One or more necessary files do not exist for gameweek {newest_gw}."
            )

        fpl_players_new_season = pd.read_csv(fpl_players_path)
        teams_pred_npxG = pd.read_csv(teams_pred_npxG_path)
        gc_probs = pd.read_csv(gc_probs_path)
        pen_share = pd.read_csv(pen_share_path)

        # Check if 'weighted_xAG' exists immediately after loading the DataFrame
        print(
            "Columns in fpl_players_new_season after loading:",
            fpl_players_new_season.columns,
        )

        # Check if 'weighted_npxG' exists in fpl_players_new_season
        if "weighted_npxG" not in fpl_players_new_season.columns:
            raise KeyError(
                f"'weighted_npxG' not found in fpl_players_new_season DataFrame columns: {fpl_players_new_season.columns}"
            )

        if "weighted_xAG" not in fpl_players_new_season.columns:
            raise KeyError(
                f"'weighted_xAG' not found in fpl_players_new_season DataFrame columns: {fpl_players_new_season.columns}"
            )

        # Define position multipliers
        position_multipliers = {
            1: 10,
            2: 6,
            3: 5,
            4: 4,
        }  # GKP, DEF, MID, FWD multipliers

        # Generate player_xp_goals
        columns_to_keep = [
            "fpl_id",
            "Player",
            "web_name",
            "Age",
            "team_name",
            "team_id",
            "element_type",
            "now_cost",
            "tsb",
            "Min",
            "90s",
            "finishing",
            "MP_new",
            "90s_new",
            "weighted_npxG",
        ]
        player_xp_goals = fpl_players_new_season[columns_to_keep].copy()

        for gw in range(1, 39):
            gw_column = str(gw)
            player_xp_goals[gw_column] = player_xp_goals.apply(
                lambda row: row["weighted_npxG"]
                * teams_pred_npxG.loc[
                    teams_pred_npxG["team_id"] == row["team_id"], gw_column
                ].values[0]
                * row["finishing"]
                * position_multipliers[row["element_type"]],
                axis=1,
            )

        player_xp_goals = player_xp_goals.round(2)

        # Generate player_xp_pens
        player_xp_pens = fpl_players_new_season[columns_to_keep].copy()

        # Merge player_xp_pens with pen_share to get the penalty share for each player
        player_xp_pens = player_xp_pens.merge(
            pen_share[["fpl_id", "pen_share"]], on="fpl_id", how="left"
        )

        # Fill missing pen_share values with 0 (players who don't take penalties)
        player_xp_pens["pen_share"] = player_xp_pens["pen_share"].fillna(0)

        for gw in range(1, 39):
            gw_column = str(gw)
            player_xp_pens[gw_column] = player_xp_pens.apply(
                lambda row: (
                    (
                        0.1
                        * teams_pred_npxG.loc[
                            teams_pred_npxG["team_id"] == row["team_id"], gw_column
                        ].values[0]
                        * 0.77
                        * position_multipliers[row["element_type"]]
                        * row["pen_share"]
                    )
                    if row["pen_share"] > 0
                    else 0
                ),  # Ensure EV is 0 if pen_share is 0
                axis=1,
            )

        player_xp_pens = player_xp_pens.round(2)

        # Generate player_xp_assists
        columns_to_keep_assists = [
            "fpl_id",
            "Player",
            "web_name",
            "Age",
            "team_name",
            "team_id",
            "element_type",
            "now_cost",
            "tsb",
            "Min",
            "90s",
            "MP_new",
            "90s_new",
            "weighted_xAG",
        ]
        player_xp_assists = fpl_players_new_season[columns_to_keep_assists].copy()

        if "weighted_xAG" not in fpl_players_new_season.columns:
            raise KeyError(
                f"'weighted_xAG' not found in fpl_players_new_season DataFrame columns: {fpl_players_new_season.columns}"
            )

        for gw in range(1, 39):
            gw_column = str(gw)
            player_xp_assists[gw_column] = player_xp_assists.apply(
                lambda row: row["weighted_xAG"]
                * teams_pred_npxG.loc[
                    teams_pred_npxG["team_id"] == row["team_id"], gw_column
                ].values[0]
                * 3,
                axis=1,
            )

        player_xp_assists = player_xp_assists.round(2)

        # Generate player_xp_cs
        columns_to_keep_cs = [
            "fpl_id",
            "Player",
            "web_name",
            "Age",
            "team_name",
            "team_id",
            "element_type",
            "now_cost",
            "tsb",
            "Min",
            "90s",
            "MP_new",
            "90s_new",
        ]
        player_xp_cs = fpl_players_new_season[columns_to_keep_cs].copy()

        points_per_goal_scenario = {
            0: {1: 4, 2: 4, 3: 1, 4: 0},
            1: 0,
            2: {1: -1, 2: -1, 3: 0, 4: 0},
            4: {1: -2, 2: -2, 3: 0, 4: 0},
            6: {1: -3, 2: -3, 3: 0, 4: 0},
            8: {1: -4, 2: -4, 3: 0, 4: 0},
        }

        for gw in range(1, 39):
            cs_column = f"{gw}_0_goals"
            gc_1_column = f"{gw}_1_goals"
            gc_2_column = f"{gw}_2_goals"
            gc_4_column = f"{gw}_4_goals"
            gc_6_column = f"{gw}_6_goals"
            gc_8_column = f"{gw}_8_goals"

            player_xp_cs[str(gw)] = player_xp_cs.apply(
                lambda row: (
                    gc_probs.loc[
                        gc_probs["team_id"] == row["team_id"], cs_column
                    ].values[0]
                    * points_per_goal_scenario[0][row["element_type"]]
                    + gc_probs.loc[
                        gc_probs["team_id"] == row["team_id"], gc_1_column
                    ].values[0]
                    * points_per_goal_scenario[1]
                    + gc_probs.loc[
                        gc_probs["team_id"] == row["team_id"], gc_2_column
                    ].values[0]
                    * points_per_goal_scenario[2][row["element_type"]]
                    + gc_probs.loc[
                        gc_probs["team_id"] == row["team_id"], gc_4_column
                    ].values[0]
                    * points_per_goal_scenario[4][row["element_type"]]
                    + gc_probs.loc[
                        gc_probs["team_id"] == row["team_id"], gc_6_column
                    ].values[0]
                    * points_per_goal_scenario[6][row["element_type"]]
                    + gc_probs.loc[
                        gc_probs["team_id"] == row["team_id"], gc_8_column
                    ].values[0]
                    * points_per_goal_scenario[8][row["element_type"]]
                ),
                axis=1,
            )

        player_xp_cs = player_xp_cs.round(2)

        # Merge all DataFrames on 'fpl_id'
        combined_df = player_xp_goals.merge(
            player_xp_pens, on=columns_to_keep, suffixes=("", "_pen")
        )
        combined_df = combined_df.merge(
            player_xp_assists, on=columns_to_keep_assists, suffixes=("", "_assist")
        )
        combined_df = combined_df.merge(
            player_xp_cs, on=columns_to_keep_cs, suffixes=("", "_cs")
        )

        # Drop duplicated columns
        combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]

        # Save combined_df to a CSV
        output_path = f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_EV_per_gw_new_season.csv"
        combined_df.to_csv(output_path, index=False)

        print(f"Data successfully combined and saved to {output_path}")
        return combined_df

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except KeyError as e:
        print(f"Key error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    newest_gw = input("Enter the newest gameweek number: ")
    calculate_player_ev(newest_gw)
