import pandas as pd
from pathlib import Path
import sys
import argparse
from collections import Counter


def read_sensitivity(options=None):

    if options is None or options.get("gw") is None:
        gw = int(input("What GW are you assessing? "))
        situation = (
            input("Is this a wildcard or preseason (GW1) solve? (y/n) ").strip().lower()
        )
    else:
        gw = options["gw"]
        situation = options.get("situation", "n").strip().lower()

    print()

    directory = "../data/results"
    # no_plans = len(os.listdir(directory))

    if situation == "n":

        buys = []
        sells = []
        move = []
        no_plans = 0

        for filename in Path(directory).glob("*.csv"):
            plan = pd.read_csv(filename)
            try:
                iter = plan.iloc[0]["iter"]
            except:
                iter = 0
            if (
                plan[(plan["week"] == gw) & (plan["transfer_in"] == 1)][
                    "name"
                ].to_list()
                == []
            ):
                buys.append({"move": "No transfer", "iter": iter})
                sells.append({"move": "No transfer", "iter": iter})
                move.append({"move": "No transfer", "iter": iter})
            else:
                buy_list = plan[(plan["week"] == gw) & (plan["transfer_in"] == 1)][
                    "name"
                ].to_list()
                buy = ", ".join(buy_list)
                buys.append({"move": buy, "iter": iter})

                sell_list = plan[(plan["week"] == gw) & (plan["transfer_out"] == 1)][
                    "name"
                ].to_list()
                sell = ", ".join(sell_list)
                sells.append({"move": sell, "iter": iter})
                move.append({"move": sell + " -> " + buy, "iter": iter})
            no_plans += 1

        print(f"Number of plans: {no_plans}")
        print()

        iter_scoring = {1: 3, 2: 2, 3: 1}

        buy_df = pd.DataFrame(buys)
        buy_pivot = buy_df.pivot_table(
            index="move", columns="iter", aggfunc="size", fill_value=0
        )
        iters = sorted(buy_df["iter"].unique())
        buy_pivot["PSB"] = buy_pivot.loc[:, iters].sum(axis=1) / buy_pivot.sum().sum()
        buy_pivot["PSB"] = buy_pivot["PSB"].apply(lambda x: f"{x:.0%}")
        buy_pivot["Score"] = buy_pivot.apply(
            lambda r: sum(r[i] * iter_scoring.get(i, 0) for i in iters), axis=1
        )
        buy_pivot.sort_values(by="Score", ascending=False, inplace=True)

        sell_df = pd.DataFrame(sells)
        sell_pivot = sell_df.pivot_table(
            index="move", columns="iter", aggfunc="size", fill_value=0
        )
        iters = sorted(sell_df["iter"].unique())
        sell_pivot["PSB"] = (
            sell_pivot.loc[:, iters].sum(axis=1) / sell_pivot.sum().sum()
        )
        sell_pivot["PSB"] = sell_pivot["PSB"].apply(lambda x: f"{x:.0%}")
        sell_pivot["Score"] = sell_pivot.apply(
            lambda r: sum(r[i] * iter_scoring.get(i, 0) for i in iters), axis=1
        )
        sell_pivot.sort_values(by="Score", ascending=False, inplace=True)

        move_df = pd.DataFrame(move)
        move_pivot = move_df.pivot_table(
            index="move", columns="iter", aggfunc="size", fill_value=0
        )
        iters = sorted(move_df["iter"].unique())
        move_pivot["PSB"] = (
            move_pivot.loc[:, iters].sum(axis=1) / move_pivot.sum().sum()
        )
        move_pivot["PSB"] = move_pivot["PSB"].apply(lambda x: f"{x:.0%}")
        move_pivot["Score"] = move_pivot.apply(
            lambda r: sum(r[i] * iter_scoring.get(i, 0) for i in iters), axis=1
        )
        move_pivot.sort_values(by="Score", ascending=False, inplace=True)

        print("Buy:")
        print(buy_pivot)
        print()
        print("Sell:")
        print(sell_pivot)
        print()
        print("Move:")
        print(move_pivot)

    elif situation == "y":

        goalkeepers = []
        defenders = []
        midfielders = []
        forwards = []

        no_plans = 0

        for filename in Path(directory).glob("*.csv"):
            plan = pd.read_csv(filename)

            # Goalkeepers list of tuples (name, lineup status)
            goalkeepers += (
                plan[
                    (plan["week"] == gw)
                    & (plan["pos"] == "GKP")
                    & (plan["transfer_out"] != 1)
                ][["name", "lineup"]]
                .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
                .to_list()
            )

            # Defenders list of tuples (name, lineup status)
            defenders += (
                plan[
                    (plan["week"] == gw)
                    & (plan["pos"] == "DEF")
                    & (plan["transfer_out"] != 1)
                ][["name", "lineup"]]
                .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
                .to_list()
            )

            # Midfielders list of tuples (name, lineup status)
            midfielders += (
                plan[
                    (plan["week"] == gw)
                    & (plan["pos"] == "MID")
                    & (plan["transfer_out"] != 1)
                ][["name", "lineup"]]
                .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
                .to_list()
            )

            # Forwards list of tuples (name, lineup status)
            forwards += (
                plan[
                    (plan["week"] == gw)
                    & (plan["pos"] == "FWD")
                    & (plan["transfer_out"] != 1)
                ][["name", "lineup"]]
                .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
                .to_list()
            )

            no_plans += 1

        print(f"Number of plans: {no_plans}")
        print()

        # Function to calculate total counts and lineup counts
        def calculate_counts(player_list):
            total_count = Counter([name for name, lineup in player_list])
            lineup_count = Counter(
                [name for name, lineup in player_list if lineup == 1]
            )

            # Convert to DataFrame
            total_df = pd.DataFrame(total_count.items(), columns=["player", "PSB"])
            lineup_df = pd.DataFrame(lineup_count.items(), columns=["player", "Lineup"])

            # Merge both DataFrames on player name
            merged_df = pd.merge(total_df, lineup_df, on="player", how="left").fillna(0)

            return merged_df

        # Calculate for each position
        keepers = calculate_counts(goalkeepers)
        defs = calculate_counts(defenders)
        mids = calculate_counts(midfielders)
        fwds = calculate_counts(forwards)

        # Function to convert counts to percentages and sort by PSB
        def calculate_percentage(df, no_plans):
            # Sort by PSB before converting to percentages
            df = df.sort_values(by="PSB", ascending=False).reset_index(drop=True)

            df["#_PSB"] = df["PSB"].astype(int)
            df["#_Lineup"] = df["Lineup"].astype(int)

            # Convert to percentage
            df["PSB"] = [
                "{:.0%}".format(df["PSB"][x] / no_plans) for x in range(df.shape[0])
            ]
            df["Lineup"] = [
                "{:.0%}".format(df["Lineup"][x] / no_plans) for x in range(df.shape[0])
            ]

            return df

        # Calculate percentages and sort for each position
        keepers = calculate_percentage(keepers, no_plans)
        defs = calculate_percentage(defs, no_plans)
        mids = calculate_percentage(mids, no_plans)
        fwds = calculate_percentage(fwds, no_plans)

        # Function to print DataFrame with aligned columns and without the redundant "player" prefix
        def print_dataframe(df, title):
            print(f"{title}:")

            # Sort the DataFrame by PSB_count in descending order
            df = df.sort_values(by="#_PSB", ascending=False).reset_index(drop=True)

            # Define the max length for each column for proper alignment
            max_name_len = df["player"].str.len().max()
            max_psb_len = 8  # PSB column is fixed at percentages, so max length is 6 (e.g., "100%")
            max_lineup_len = 8  # Lineup column is also percentages, so max length is 6
            max_psb_count_len = max(
                8, df["#_PSB"].astype(str).str.len().max()
            )  # Minimum length of 10
            max_lineup_count_len = max(
                8, df["#_Lineup"].astype(str).str.len().max()
            )  # Minimum length of 10

            # Print the headers first with fixed width formatting
            print(
                f"{'player':<{max_name_len}} {'PSB':<{max_psb_len}} {'Lineup':<{max_lineup_len}} "
                f"{'#_PSB':<{max_psb_count_len}} {'#_Lineup':<{max_lineup_count_len}}"
            )

            # Ensure PSB and Lineup are strings and handle any non-string values
            df["PSB"] = df["PSB"].astype(str)
            df["Lineup"] = df["Lineup"].astype(str)

            # Normalize values for PSB and Lineup to range [0, 1]
            try:
                # Extract percentage part from the "PSB" column (e.g., '50% (10)' -> '50')
                df["PSB_normalized"] = (
                    df["PSB"].str.extract(r"(\d+)%")[0].astype(float) / 100
                )

                # Extract percentage part from the "Lineup" column (e.g., '80% (8)' -> '80')
                df["Lineup_normalized"] = (
                    df["Lineup"].str.extract(r"(\d+)%")[0].astype(float) / 100
                )
            except Exception as e:
                print(f"Error normalizing data: {e}")
                return

            # Filter out players with PSB less than 5%
            df = df[df["PSB_normalized"] >= 0.05]

            # Calculate the maximum normalized values for the current DataFrame
            max_normalized_psb = df["PSB_normalized"].max() if not df.empty else 1
            max_normalized_lineup = df["Lineup_normalized"].max() if not df.empty else 1

            # Print each row with calculated widths and color intensity based on normalized values
            for index, row in df.iterrows():
                # Calculate brightness for PSB based on its maximum value
                brightness_psb = (
                    int(200 * (row["PSB_normalized"] / max_normalized_psb))
                    if max_normalized_psb > 0
                    else 200
                )

                # Calculate brightness for Lineup based on its maximum value
                brightness_lineup = (
                    int(200 * (row["Lineup_normalized"] / max_normalized_lineup))
                    if max_normalized_lineup > 0
                    else 200
                )

                # Define colors for both PSB and Lineup
                color_psb = f"\033[38;2;0;{brightness_psb};{255 - brightness_psb}m"  # Blue to Green gradient for PSB
                color_lineup = f"\033[38;2;0;{brightness_lineup};{255 - brightness_lineup}m"  # Blue to Green gradient for Lineup

                print(
                    f"{row['player']:<{max_name_len}} "
                    f"{color_psb}{row['PSB']:<{max_psb_len}}\033[0m "
                    f"{color_lineup}{row['Lineup']:<{max_lineup_len}}\033[0m "
                    f"{color_psb}{row['#_PSB']:<{max_psb_count_len}}\033[0m "
                    f"{color_lineup}{row['#_Lineup']:<{max_lineup_count_len}}\033[0m"
                )
            print()  # Add an empty line for separation between tables

        # Print sorted DataFrames for each position with proper alignment
        print_dataframe(keepers, "Goalkeepers")
        print_dataframe(defs, "Defenders")
        print_dataframe(mids, "Midfielders")
        print_dataframe(fwds, "Forwards")

        return {"keepers": keepers, "defs": defs, "mids": mids, "fwds": fwds}

    else:
        print(
            "Invalid input, please enter 'y' for a wildcard or 'n' for a regular transfer plan."
        )


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Summarize sensitivity analysis results"
        )
        parser.add_argument("--gw", type=int, help="Numeric value for 'gw'")
        parser.add_argument(
            "--wildcard",
            choices=["Y", "y", "N", "n"],
            help="'Y' if using wildcard, 'N' otherwise",
        )
        args = parser.parse_args()
        gw_value = args.gw
        is_wildcard = args.wildcard
        read_sensitivity({"gw": gw_value, "situation": is_wildcard})
    except:
        read_sensitivity()
