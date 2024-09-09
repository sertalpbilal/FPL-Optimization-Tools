import pandas as pd
import os
import requests
import numpy as np


def calculate_player_ev(newest_gw):
    try:
        # Load the necessary CSV files
        fpl_players_path = f"C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/fpl_players_new_season_gw{newest_gw}.csv"
        teams_pred_npxG_path = f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/teams_pred_npxG_gw{newest_gw}.csv"
        gc_probs_path = f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/GC_probabilities.csv"
        pen_share_path = f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/pen_share.csv"
        xmins_path = f"C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data/fpl_players_xmins.csv"

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
        player_xmins = pd.read_csv(xmins_path)

        fpl_players_new_season = fpl_players_new_season.dropna(
            subset=["weighted_npxG", "weighted_xAG"]
        )

        fpl_players_new_season = fpl_players_new_season.merge(
            player_xmins[["fpl_id", "xMins"]], on="fpl_id", how="left"
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
            "position",
            "now_cost",
            "tsb",
            "Min",
            "90s",
            "finishing",
            "xMins",
            "MP_new",
            "90s_new",
            "weighted_npxG",
            "weighted_xAG",
        ]
        player_xp_goals = fpl_players_new_season[columns_to_keep].copy()

        for gw in range(1, 39):
            gw_column = str(gw)
            player_xp_goals[gw_column] = player_xp_goals.apply(
                lambda row: row["weighted_npxG"]
                * row["xMins"]
                / 90
                * teams_pred_npxG.loc[
                    teams_pred_npxG["team_id"] == row["team_id"], gw_column
                ].values[0]
                * row["finishing"]
                * position_multipliers[row["element_type"]],
                axis=1,
            )

        player_xp_goals = player_xp_goals.round(2)

        # player_xp_goals.drop(["weighted_npxG"], axis=1, inplace=True)

        player_xp_goals.to_csv(
            f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_xp_goals_gw{newest_gw}.csv",
            index=False,
        )

        print(f"Generated player_xp_goals_gw{newest_gw}.csv")

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

        # player_xp_pens.drop(["weighted_npxG"], axis=1, inplace=True)

        player_xp_pens.to_csv(
            f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_xp_pens_gw{newest_gw}.csv",
            index=False,
        )

        print(f"Generated player_xp_pens_gw{newest_gw}.csv")

        player_xp_assists = fpl_players_new_season[columns_to_keep].copy()

        for gw in range(1, 39):
            gw_column = str(gw)
            player_xp_assists[gw_column] = player_xp_assists.apply(
                lambda row: row["weighted_xAG"]
                * row["xMins"]
                / 90
                * teams_pred_npxG.loc[
                    teams_pred_npxG["team_id"] == row["team_id"], gw_column
                ].values[0]
                * 3,
                axis=1,
            )

        player_xp_assists = player_xp_assists.round(2)

        # player_xp_assists.drop(columns=["weighted_xAG"], inplace=True)

        player_xp_assists.to_csv(
            f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_xp_assists_gw{newest_gw}.csv",
            index=False,
        )

        print(f"Generated player_xp_assists_gw{newest_gw}.csv")

        player_xp_cs = fpl_players_new_season[columns_to_keep].copy()

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
                    * player_xmins.loc[
                        player_xmins["fpl_id"] == row["fpl_id"], "P(60_min)"
                    ].values[0]
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

        player_xp_cs.to_csv(
            f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_xp_cs_gw{newest_gw}.csv",
            index=False,
        )

        print(f"Generated player_xp_cs_gw{newest_gw}.csv")

        player_xp_app = fpl_players_new_season[columns_to_keep].copy()

        for gw in range(1, 39):
            gw_column = str(gw)
            player_xp_app[gw_column] = player_xp_app.apply(
                lambda row: (
                    player_xmins.loc[
                        player_xmins["fpl_id"] == row["fpl_id"], "P(1_min)"
                    ].values[0]
                    * 1
                )
                + (
                    player_xmins.loc[
                        player_xmins["fpl_id"] == row["fpl_id"], "P(60_min)"
                    ].values[0]
                    * 1
                ),
                axis=1,
            )

        player_xp_app = player_xp_app.round(2)

        player_xp_app.to_csv(
            f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_xp_app_gw{newest_gw}.csv",
            index=False,
        )

        print(f"Generated player_xp_app_gw{newest_gw}.csv")

        # Step 1: Define common columns to retain without prefixes
        common_columns = [
            # "fbref",
            "fpl_id",
            "Player",
            "web_name",
            # "Age",
            "team_name",
            # "team_id",
            "position",
            "now_cost",
            "tsb",
            # "Min",
            # "90s",
            "finishing",
            "xMins",
            # "MP_new",
            # "90s_new",
            "weighted_npxG",
            "weighted_xAG",
        ]

        # Step 2: Add prefixes only to the gameweek columns, not to the common columns
        def rename_gameweek_columns(df, prefix):
            df_prefixed = df.copy()
            # Rename only the gameweek columns with the provided prefix
            gameweek_columns = [col for col in df.columns if col not in common_columns]
            df_prefixed.rename(
                columns={col: f"{prefix}_{col}" for col in gameweek_columns},
                inplace=True,
            )
            return df_prefixed

        player_xp_goals_prefixed = rename_gameweek_columns(player_xp_goals, "goals")
        player_xp_pens_prefixed = rename_gameweek_columns(player_xp_pens, "pens")
        player_xp_assists_prefixed = rename_gameweek_columns(
            player_xp_assists, "assists"
        )
        player_xp_cs_prefixed = rename_gameweek_columns(player_xp_cs, "cs")
        player_xp_app_prefixed = rename_gameweek_columns(player_xp_app, "app")

        # Step 3: Merge the dataframes on the common columns
        merged_df = player_xp_goals_prefixed.merge(
            player_xp_pens_prefixed, on=common_columns, how="outer"
        )
        merged_df = merged_df.merge(
            player_xp_assists_prefixed, on=common_columns, how="outer"
        )
        merged_df = merged_df.merge(
            player_xp_cs_prefixed, on=common_columns, how="outer"
        )

        merged_df = merged_df.merge(
            player_xp_app_prefixed, on=common_columns, how="outer"
        )

        # Step 4: Add total columns (sum of goals, pens, assists, cs for each gameweek)
        num_gameweeks = 38  # Assuming 38 gameweeks, adjust this if needed
        for gw in range(1, num_gameweeks + 1):
            gw_cols = [
                f"goals_{gw}",
                f"pens_{gw}",
                f"assists_{gw}",
                f"cs_{gw}",
                f"app_{gw}",
            ]
            # Check if these columns exist in the dataframe (in case some columns are missing for certain gameweeks)
            if all(col in merged_df.columns for col in gw_cols):
                merged_df[f"total_{gw}"] = merged_df[gw_cols].sum(axis=1)

        # Step 5: Reorder the columns so common columns come first and the gameweek columns follow in a specific order
        # Extract all the columns from merged_df
        all_columns = merged_df.columns.tolist()

        # Separate common columns and gameweek columns
        gw_columns = [col for col in all_columns if col not in common_columns]

        # Desired order within each gameweek
        metric_order = ["goals", "pens", "assists", "cs", "app", "total"]

        # Function to extract the numerical part of the column names
        def extract_number(col):
            try:
                return int(col.split("_")[1])
            except (IndexError, ValueError):
                return float("inf")

        # Sort the gameweek columns first by gameweek number, then by the desired metric order
        ordered_gw_columns = sorted(
            gw_columns,
            key=lambda x: (extract_number(x), metric_order.index(x.split("_")[0])),
        )

        # Order: common_columns first, then the ordered gameweek columns
        ordered_columns = common_columns + ordered_gw_columns

        # Reorder the merged dataframe
        merged_df = merged_df[ordered_columns]

        # Step 6: Inspect the final merged dataframe
        # print(merged_df.head(10))

        # Step 7: Save the merged dataframe to a CSV file
        merged_df.to_csv(
            f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_ev_gw{newest_gw}.csv",
            index=False,
        )

        print(
            f"Player expected values for all metrics merged and saved successfully for gameweek {newest_gw}."
        )

        totals_columns = [f"total_{gw}" for gw in range(1, num_gameweeks + 1)]

        new_ordered_columns = common_columns + totals_columns

        merged_df_totals = merged_df[new_ordered_columns]

        # Rename columns by removing the 'total_' prefix
        merged_df_totals.columns = [
            col.replace("total_", "") for col in merged_df_totals.columns
        ]

        merged_df_totals.to_csv(
            f"C:/Users/erknud3/fpl-optimization/model/data/Prediction_Data/player_ev_totals_gw{newest_gw}.csv",
            index=False,
        )

        print(
            f"Player expected values for totals saved successfully for gameweek {newest_gw}."
        )

        static_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        r = requests.get(static_url).json()
        teams = r["teams"]

        # Process the DataFrame
        data = (
            merged_df_totals.copy()
        )  # Create a copy of merged_df_totals to avoid modifying the original DataFrame
        data.columns = [
            col.strip() for col in data.columns
        ]  # Strip whitespace from column names

        data.loc[:, "now_cost"] = pd.to_numeric(data["now_cost"], errors="coerce")

        pos_fix = {"GKP": "G", "DEF": "D", "MID": "M", "FWD": "F"}
        data.loc[:, "position"] = data["position"].replace(pos_fix)

        gws = []
        for i in data.columns:
            if i.isdigit():  # Check if the column name is a digit
                if data[i].dtype == "object":
                    data.loc[:, f"{i}_Pts"] = (
                        data[i].str.strip().replace({"-": 0}).astype(float)
                    )
                else:
                    data.loc[:, f"{i}_Pts"] = data[i].replace({"-": 0}).astype(float)

                if data["xMins"].dtype == "object":
                    data.loc[:, f"{i}_xMins"] = (
                        data["xMins"]
                        .str.strip()
                        .replace({"-": 0})
                        .astype(float)
                        .replace({np.nan: 0})
                    )
                else:
                    data.loc[:, f"{i}_xMins"] = (
                        data["xMins"]
                        .replace({"-": 0})
                        .astype(float)
                        .replace({np.nan: 0})
                    )
                gws.append(i)

        data["Name"] = data["Player"]
        data["Value"] = data["now_cost"]
        data["Pos"] = data["position"]
        data["review_id"] = data["fpl_id"]

        df_final = data[
            ["review_id", "Name", "Pos", "Value"]
            + [f"{gw}_{tag}" for gw in gws for tag in ["Pts", "xMins"]]
        ].copy()

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

        df_final.to_csv("C:/Users/erknud3/fpl-optimization/data/garz.csv", index=True)

        print("Data succesfully converted to review format and saved to 'garz.csv'")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except KeyError as e:
        print(f"Key error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    newest_gw = input("Enter the newest gameweek number: ")
    calculate_player_ev(newest_gw)
