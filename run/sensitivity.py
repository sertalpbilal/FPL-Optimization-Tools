import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

from paths import DATA_DIR

ITER_SCORING = {0: 10, 1: 9, 2: 8}


def get_user_inputs(options=None):
    """Get user inputs for sensitivity analysis."""
    if options is None:
        options = {}

    gw = options.get("gw")
    situation = options.get("situation")

    if gw is not None and situation is not None:
        all_gws = "n"
    else:
        all_gws = options.get("all_gws")
        if all_gws is None:
            all_gws = input("Do you want to display a summary of buys and sells for all GWs? (y/n) ").strip().lower()

    print()
    return all_gws, gw, situation


def process_all_gameweeks():
    """Process and display results for all gameweeks."""
    directory = DATA_DIR / "results"

    buys = []
    sells = []
    move = []
    no_plans = 0
    gameweeks = set()

    # Read CSV files and process plans
    for filename in Path(directory).glob("*.csv"):
        plan = pd.read_csv(filename)
        plan = plan.loc[(plan["squad"] == 1) | (plan["transfer_out"] == 1)]
        plan = plan.sort_values(by=["week", "iter", "pos", "id"])
        iteration = plan.iloc[0]["iter"] if not plan.empty else 0
        gameweeks.update(plan["week"].unique())

        for week in gameweeks:
            if plan[(plan["week"] == week) & (plan["transfer_in"] == 1)]["name"].to_list() == []:
                buys.append({"move": "No transfer", "iter": iteration, "week": week})
                sells.append({"move": "No transfer", "iter": iteration, "week": week})
                move.append({"move": "No transfer", "iter": iteration, "week": week})
            else:
                buy_list = plan[(plan["week"] == week) & (plan["transfer_in"] == 1)]["name"].to_list()
                for buy in buy_list:
                    buys.append({"move": buy, "iter": iteration, "week": week})

                sell_list = plan[(plan["week"] == week) & (plan["transfer_out"] == 1)]["name"].to_list()
                for sell in sell_list:
                    sells.append({"move": sell, "iter": iteration, "week": week})
                    move.append(
                        {
                            "move": sell + " -> " + ", ".join(buy_list),
                            "iter": iteration,
                            "week": week,
                        }
                    )

        no_plans += 1

    return buys, sells, move, no_plans


def print_pivot_tables_all_gws(buy_df, sell_df, no_plans):
    """Print pivot tables for all gameweeks analysis."""
    show_top_n = input("Show top N results (y/n)? ").strip().lower()

    if show_top_n == "y":
        top_n = int(input("What do you want to use as N? "))

    def print_pivots(df, title):
        print(f"{title}:")

        # Create the pivot table with counts
        df_counts = df.pivot_table(index="move", columns="week", aggfunc="size", fill_value=0)

        # Calculate percentages
        df_percentages = df_counts.divide(no_plans).multiply(100)

        # Map percentages to display with 0 decimals, hide 0%
        df_percentages = df_percentages.map(lambda x: f"{x:.0f}%" if x != 0 else "")

        # Store numeric version for sorting and total calculations
        df_percentages_numeric = df_counts.divide(no_plans).multiply(100)

        # Add 'Total' column summing over all weeks
        df_percentages["Total"] = df_percentages_numeric.sum(axis=1)
        df_percentages["Total"] = pd.to_numeric(df_percentages["Total"])

        # Sort by 'Total' column
        df_percentages.sort_values(by="Total", ascending=False, inplace=True)

        # Apply the top N filter if requested
        if show_top_n == "y":
            df_percentages = df_percentages.head(top_n)

        # Format 'Total' column as percentages
        df_percentages["Total"] = df_percentages["Total"].map(lambda x: f"{x:.0f}%")

        # Print the result
        print(df_percentages)
        print()

    # Display the results
    print()
    print(f"Number of plans: {no_plans}")
    print()

    # Print Buy and Sell pivots
    print_pivots(buy_df, "Buy")
    print_pivots(sell_df, "Sell")


def process_single_gameweek(gw, situation):
    """Process and display results for a single gameweek."""
    directory = DATA_DIR / "results"

    if situation == "n":
        return process_regular_transfers(gw, directory)
    elif situation == "y":
        return process_wildcard_transfers(gw, directory)
    else:
        print("Invalid input, please enter 'y' for a wildcard or 'n' for a regular transfer plan.")
        return None


def process_regular_transfers(gw, directory):
    """Process regular transfer analysis for a specific gameweek."""
    print(f"Processing for GW {gw} without wildcard.")

    buys = []
    sells = []
    move = []
    no_plans = 0

    for filename in Path(directory).glob("*.csv"):
        plan = pd.read_csv(filename)
        plan = plan.loc[(plan["squad"] == 1) | (plan["transfer_out"] == 1)]
        plan = plan.sort_values(by=["week", "iter", "pos", "id"])
        try:
            iteration = plan.iloc[0]["iter"]
        except Exception:
            iteration = 0

        if plan[(plan["week"] == gw) & (plan["transfer_in"] == 1)]["name"].to_list() == []:
            buys.append({"move": "No transfer", "iter": iteration})
            sells.append({"move": "No transfer", "iter": iteration})
            move.append({"move": "No transfer", "iter": iteration})
        else:
            buy_list = plan[(plan["week"] == gw) & (plan["transfer_in"] == 1)]["name"].to_list()
            buy = ", ".join(buy_list)
            buys.append({"move": buy, "iter": iteration})
            sell_list = plan[(plan["week"] == gw) & (plan["transfer_out"] == 1)]["name"].to_list()
            sell = ", ".join(sell_list)
            sells.append({"move": sell, "iter": iteration})
            move.append({"move": sell + " -> " + buy, "iter": iteration})
        no_plans += 1

    print()
    print(f"Number of plans: {no_plans}")
    print()

    return create_regular_transfer_pivots(buys, sells, move, no_plans)


def create_regular_transfer_pivots(buys, sells, move, no_plans):
    """Create and display pivot tables for regular transfers."""
    buy_df = pd.DataFrame(buys)
    buy_pivot = buy_df.pivot_table(index="move", columns="iter", aggfunc="size", fill_value=0)
    iters = sorted(buy_df["iter"].unique())
    buy_pivot["PSB"] = buy_pivot.loc[:, iters].sum(axis=1) / buy_pivot.sum().sum()
    buy_pivot["PSB"] = buy_pivot["PSB"].apply(lambda x: f"{x:.0%}")
    buy_pivot["Score"] = buy_pivot.apply(lambda r: sum(r[i] * ITER_SCORING.get(i, 0) for i in iters), axis=1)
    buy_pivot.sort_values(by="Score", ascending=False, inplace=True)

    sell_df = pd.DataFrame(sells)
    sell_pivot = sell_df.pivot_table(index="move", columns="iter", aggfunc="size", fill_value=0)
    iters = sorted(sell_df["iter"].unique())
    sell_pivot["PSB"] = sell_pivot.loc[:, iters].sum(axis=1) / sell_pivot.sum().sum()
    sell_pivot["PSB"] = sell_pivot["PSB"].apply(lambda x: f"{x:.0%}")
    sell_pivot["Score"] = sell_pivot.apply(lambda r: sum(r[i] * ITER_SCORING.get(i, 0) for i in iters), axis=1)
    sell_pivot.sort_values(by="Score", ascending=False, inplace=True)

    move_df = pd.DataFrame(move)
    move_pivot = move_df.pivot_table(index="move", columns="iter", aggfunc="size", fill_value=0)
    iters = sorted(move_df["iter"].unique())
    move_pivot["PSB"] = move_pivot.loc[:, iters].sum(axis=1) / move_pivot.sum().sum()
    move_pivot["PSB"] = move_pivot["PSB"].apply(lambda x: f"{x:.0%}")
    move_pivot["Score"] = move_pivot.apply(lambda r: sum(r[i] * ITER_SCORING.get(i, 0) for i in iters), axis=1)
    move_pivot.sort_values(by="Score", ascending=False, inplace=True)

    # Set the display options for wider column width
    pd.set_option("display.max_colwidth", None)

    # Ask once for filtering choice at the beginning
    show_top_n = input("Show top N results (y/n)? ").strip().lower()

    if show_top_n == "y":
        top_n = int(input("What do you want to use as N? "))
        print()

    # Apply the top N filter if requested
    if show_top_n == "y":
        buy_pivot = buy_pivot.head(top_n)
        sell_pivot = sell_pivot.head(top_n)
        move_pivot = move_pivot.head(top_n)

    print("Buy:")
    print(buy_pivot)
    print()
    print("Sell:")
    print(sell_pivot)
    print()
    print("Move:")
    print(move_pivot)
    print()

    return {"buy_pivot": buy_pivot, "sell_pivot": sell_pivot, "move_pivot": move_pivot}


def process_wildcard_transfers(gw, directory):
    """Process wildcard transfer analysis for a specific gameweek."""
    print(f"Processing for GW {gw} with wildcard.")

    goalkeepers = []
    defenders = []
    midfielders = []
    forwards = []
    no_plans = 0

    for filename in Path(directory).glob("*.csv"):
        plan = pd.read_csv(filename)
        plan = plan.loc[(plan["squad"] == 1) | (plan["transfer_out"] == 1)]

        # Goalkeepers list of tuples (name, lineup status)
        goalkeepers += (
            plan[(plan["week"] == gw) & (plan["pos"] == "GKP") & (plan["transfer_out"] != 1)][["name", "lineup"]]
            .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
            .to_list()
        )
        # Defenders list of tuples (name, lineup status)
        defenders += (
            plan[(plan["week"] == gw) & (plan["pos"] == "DEF") & (plan["transfer_out"] != 1)][["name", "lineup"]]
            .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
            .to_list()
        )
        # Midfielders list of tuples (name, lineup status)
        midfielders += (
            plan[(plan["week"] == gw) & (plan["pos"] == "MID") & (plan["transfer_out"] != 1)][["name", "lineup"]]
            .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
            .to_list()
        )
        # Forwards list of tuples (name, lineup status)
        forwards += (
            plan[(plan["week"] == gw) & (plan["pos"] == "FWD") & (plan["transfer_out"] != 1)][["name", "lineup"]]
            .apply(lambda x: (x["name"], 1 if x["lineup"] == 1 else 0), axis=1)
            .to_list()
        )
        no_plans += 1

    print()
    print(f"Number of plans: {no_plans}")
    print()

    return create_wildcard_pivots(goalkeepers, defenders, midfielders, forwards, no_plans)


def calculate_counts(player_list):
    """Calculate total counts and lineup counts for players."""
    total_count = Counter([name for name, lineup in player_list])
    lineup_count = Counter([name for name, lineup in player_list if lineup == 1])
    # Convert to DataFrame
    total_df = pd.DataFrame(total_count.items(), columns=["player", "PSB"])
    lineup_df = pd.DataFrame(lineup_count.items(), columns=["player", "Lineup"])
    # Merge both DataFrames on player name
    merged_df = pd.merge(total_df, lineup_df, on="player", how="left").fillna(0)
    return merged_df


def calculate_percentage(df, no_plans):
    """Convert counts to percentages and sort by PSB."""
    # Sort by PSB before converting to percentages
    df = df.sort_values(by="PSB", ascending=False).reset_index(drop=True)
    df["#_PSB"] = df["PSB"].astype(int)
    df["#_Lineup"] = df["Lineup"].astype(int)
    # Convert to percentage
    df["PSB"] = ["{:.0%}".format(df["PSB"][x] / no_plans) for x in range(df.shape[0])]
    df["Lineup"] = ["{:.0%}".format(df["Lineup"][x] / no_plans) for x in range(df.shape[0])]
    return df


def print_dataframe(df, title, use_color=False, psb_threshold=0.05):
    """Print DataFrame with aligned columns and optional color grading."""
    print(f"{title}:")
    # Sort the DataFrame by PSB_count in descending order
    df = df.sort_values(by="#_PSB", ascending=False).reset_index(drop=True)
    # Define the max length for each column for proper alignment
    max_name_len = df["player"].str.len().max()
    max_psb_len = 8
    max_lineup_len = 8
    max_psb_count_len = max(8, df["#_PSB"].astype(str).str.len().max())
    max_lineup_count_len = max(8, df["#_Lineup"].astype(str).str.len().max())
    # Print the headers first with fixed width formatting
    header_format = (
        f"{'player':<{max_name_len}} "
        f"{'PSB':<{max_psb_len}} "
        f"{'Lineup':<{max_lineup_len}} "
        f"{'#_PSB':<{max_psb_count_len}} "
        f"{'#_Lineup':<{max_lineup_count_len}}"
    )
    print(header_format)
    # Ensure PSB and Lineup are strings and handle any non-string values
    df["PSB"] = df["PSB"].astype(str)
    df["Lineup"] = df["Lineup"].astype(str)
    # Normalize values for PSB and Lineup to range [0, 1]
    try:
        df["PSB_normalized"] = df["PSB"].str.extract(r"(\d+)%")[0].astype(float) / 100
        df["Lineup_normalized"] = df["Lineup"].str.extract(r"(\d+)%")[0].astype(float) / 100
    except Exception as e:
        print(f"Error normalizing data: {e}")
        return
    # Filter out players with PSB less than 5%
    df = df[df["PSB_normalized"] >= psb_threshold]
    # Calculate the maximum normalized values for the current DataFrame
    max_normalized_psb = df["PSB_normalized"].max() if not df.empty else 1
    max_normalized_lineup = df["Lineup_normalized"].max() if not df.empty else 1
    # Print each row with calculated widths and optional color grading
    for _, row in df.iterrows():
        if use_color:
            # Calculate brightness for PSB based on its maximum value
            brightness_psb = int(200 * (row["PSB_normalized"] / max_normalized_psb)) if max_normalized_psb > 0 else 200
            # Calculate brightness for Lineup based on its maximum value
            brightness_lineup = int(200 * (row["Lineup_normalized"] / max_normalized_lineup)) if max_normalized_lineup > 0 else 200
            # Define colors for both PSB and Lineup
            color_psb = f"\033[38;2;0;{brightness_psb};{255 - brightness_psb}m"  # Blue to Green gradient for PSB
            color_lineup = f"\033[38;2;0;{brightness_lineup};{255 - brightness_lineup}m"  # Blue to Green gradient for Lineup
        else:
            # No color formatting if use_color is False
            color_psb = color_lineup = ""
        # Print each row with or without color
        player_part = f"{row['player']:<{max_name_len}}"
        psb_part = f"{color_psb}{row['PSB']:<{max_psb_len}}\033[0m"
        lineup_part = f"{color_lineup}{row['Lineup']:<{max_lineup_len}}\033[0m"
        psb_count_part = f"{color_psb}{row['#_PSB']:<{max_psb_count_len}}\033[0m"
        lineup_count_part = f"{color_lineup}{row['#_Lineup']:<{max_lineup_count_len}}\033[0m"

        print(f"{player_part} {psb_part} {lineup_part} {psb_count_part} {lineup_count_part}")
    print()  # Add an empty line for separation between tables


def create_wildcard_pivots(goalkeepers, defenders, midfielders, forwards, no_plans):
    """Create and display pivot tables for wildcard transfers."""
    # Calculate for each position
    keepers = calculate_counts(goalkeepers)
    defs = calculate_counts(defenders)
    mids = calculate_counts(midfielders)
    fwds = calculate_counts(forwards)

    # Calculate percentages and sort for each position
    keepers = calculate_percentage(keepers, no_plans)
    defs = calculate_percentage(defs, no_plans)
    mids = calculate_percentage(mids, no_plans)
    fwds = calculate_percentage(fwds, no_plans)

    # Print sorted DataFrames for each position with proper alignment
    print_dataframe(keepers, "Goalkeepers")
    print_dataframe(defs, "Defenders")
    print_dataframe(mids, "Midfielders")
    print_dataframe(fwds, "Forwards")

    return {"keepers": keepers, "defs": defs, "mids": mids, "fwds": fwds}


def read_sensitivity(options=None):
    """Main function to read and process sensitivity analysis."""
    all_gws, gw, situation = get_user_inputs(options)

    # If all_gws is 'y', gw and wildcard are not needed
    if all_gws == "y":
        print("Processing all gameweeks.")
        buys, sells, move, no_plans = process_all_gameweeks()
        buy_df = pd.DataFrame(buys)
        sell_df = pd.DataFrame(sells)
        print_pivot_tables_all_gws(buy_df, sell_df, no_plans)

    # If all_gws is 'n', use gw and situation or ask for them
    else:
        if gw is None:
            gw = int(input("What GW are you assessing? "))
        if situation is None:
            situation = input("Is this a wildcard or preseason (GW1) solve? (y/n) ").strip().lower()

        return process_single_gameweek(gw, situation)


if __name__ == "__main__":
    import argparse

    try:
        parser = argparse.ArgumentParser(description="Summarize sensitivity analysis results")
        parser.add_argument(
            "--all_gws",
            choices=["Y", "y", "N", "n"],
            help="'y' if you want to display all gameweeks, 'n' otherwise",
        )
        parser.add_argument("--gw", type=int, help="Numeric value for 'gw'")
        parser.add_argument(
            "--wildcard",
            choices=["Y", "y", "N", "n"],
            help="'y' if using wildcard, 'n' otherwise",
        )
        args = parser.parse_args()

        # Prepare options for read_sensitivity based on arguments
        options = {}

        # Handle command-line arguments
        if args.all_gws:
            options["all_gws"] = args.all_gws.strip().lower()

        if args.gw is not None:
            options["gw"] = args.gw

        if args.wildcard:
            options["situation"] = args.wildcard.strip().lower()

        # If no command-line arguments are provided, prompt for input
        if not any(vars(args).values()):
            print("No command-line arguments provided, prompting for input... use command line arguments if you want to skip questions")
            print()
            read_sensitivity()  # Prompt for input
        elif "all_gws" in options or ("gw" in options and "situation" in options):
            read_sensitivity(options)
        else:
            print("Error: You must specify either --all_gws or both --gw and --wildcard.")

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Falling back to user input mode.")

        # Fallback to prompt user for input
        read_sensitivity()
