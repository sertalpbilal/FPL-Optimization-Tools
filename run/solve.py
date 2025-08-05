import argparse
import csv
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

import pandas as pd
import requests

from dev.solver import generate_team_json, prep_data, solve_multi_period_fpl
from dev.visualization import create_squad_timeline
from utils import get_random_id, load_config_files, load_settings

IS_COLAB = "COLAB_GPU" in os.environ
BINARY_THRESHOLD = 0.5


def is_latest_version():
    try:
        # Get the current branch name
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()

        # Fetch the latest updates from the remote
        subprocess.run(["git", "fetch"], check=True, stderr=subprocess.DEVNULL)

        # Check if there are commits in the remote branch not in the local branch
        updates = subprocess.check_output(["git", "rev-list", f"HEAD..origin/{branch}"], stderr=subprocess.DEVNULL, text=True).strip()

        if updates:
            print("Your repository is not up-to-date. Please pull the latest changes.")
            return False
        else:
            print("Your repository is up-to-date.")
            return True
    except subprocess.CalledProcessError:
        print("Error: Could not check the repository status.")
        return False


def solve_regular(runtime_options=None):
    # if not IS_COLAB:
    #     print("Checking for updates...")
    #     is_latest_version()

    base_folder = pathlib.Path()
    sys.path.append(str(base_folder / "../dev"))

    # Create a base parser first for the --config argument
    # remaining_args is all the command line args that aren't --config
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--config", type=str, help="Path to one or more configuration files (semicolon-delimited)")
    base_args, remaining_args = base_parser.parse_known_args()

    # Load base configuration file
    if IS_COLAB:
        with open("settings.json") as f:
            options = json.load(f)
    else:
        options = load_settings()

    # Load and merge additional configuration files if specified
    if base_args.config:
        config_options = load_config_files(base_args.config)
        options.update(config_options)  # Override base config with additional configs

    # Create the full parser with all configuration options
    parser = argparse.ArgumentParser(parents=[base_parser])
    for key, value in options.items():
        if value is None or isinstance(value, list | dict):
            parser.add_argument(f"--{key}", default=value)
            continue
        parser.add_argument(f"--{key}", type=type(value), default=value)

    # Parse remaining arguments, which will take highest priority
    args = vars(parser.parse_args(remaining_args))

    # this code block is to look at command line arguments (read as a string) and determine what type
    # they should be when there is no default argument type set by the code above
    for key, value in args.items():
        if key not in options:
            continue
        if value == options[key]:  # skip anything that hasn't been edited by command line argument
            continue

        if options[key] is None or isinstance(options[key], list | dict):
            if value.isdigit():
                args[key] = int(value)
                continue

            try:
                args[key] = float(value)
                continue
            except ValueError:
                pass

            if value[0] in "[{":
                try:
                    args[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    args[key] = json.loads(value.replace("'", '"'))
                    continue
                finally:
                    pass

            print(f"Problem with CL argument: {key}. Original value: {options[key]}, New value: {value}")

    cli_options = {k: v for k, v in args.items() if v is not None and k != "config"}

    # Update options with CLI arguments (highest priority)
    options.update(cli_options)

    if runtime_options is not None:
        options.update(runtime_options)

    if options.get("preseason"):
        my_data = {"picks": [], "chips": [], "transfers": {"limit": None, "cost": 4, "bank": 1000, "value": 0}}
    elif options.get("team_data", "json").lower() == "id":
        team_id = options.get("team_id", None)
        if team_id is None:
            print("You must supply your team_id in data/user_settings.json")
            sys.exit(0)
        my_data = generate_team_json(team_id, options)
    else:
        try:
            with open("../data/team.json") as f:
                my_data = json.load(f)
            price_changes = options.get("price_changes", [])
            if price_changes:
                my_squad_ids = [x["element"] for x in my_data["picks"]]
                with requests.Session() as s:
                    r = s.get("https://fantasy.premierleague.com/api/bootstrap-static/").json()["elements"]
                current_prices = {x["id"]: x["now_cost"] for x in r if x["id"] in my_squad_ids}
                for pid, change in price_changes:
                    if pid not in my_squad_ids:
                        continue
                    new_price = current_prices[pid] + change
                    player = next(x for x in my_data["picks"] if x["element"] == pid)
                    if player["purchase_price"] >= new_price:
                        player["selling_price"] = new_price
                    else:
                        player["selling_price"] = player["purchase_price"] + (new_price - player["purchase_price"]) // 2
        except FileNotFoundError:
            print(
                """You must either:
                        1. Download your team data from https://fantasy.premierleague.com/api/my-team/YOUR-TEAM-ID/ and
                            save it under data folder with name 'team.json', or
                        2. Set "team_data" in user_settings to "ID", and set the "team_id" value to your team's ID
                    """
            )
            sys.exit(0)
    data = prep_data(my_data, options)

    response = solve_multi_period_fpl(data, options)
    run_id = get_random_id(5)
    options["run_id"] = run_id
    for result in response:
        print(result["summary"])
        iteration = result["iter"]
        time_now = datetime.datetime.now()
        stamp = time_now.strftime("%Y-%m-%d_%H-%M-%S")
        if not (os.path.exists("../data/results/")):
            os.mkdir("../data/results/")

        solve_name = options.get("solve_name", "regular")
        if options.get("binary_file_name"):
            bfn = options.get("binary_file_name")
            filename = f"{solve_name}_{bfn}_{stamp}_{run_id}_{iteration}"
        else:
            filename = f"{solve_name}_{stamp}_{run_id}_{iteration}"
        result["picks"].to_csv("../data/results/" + filename + ".csv")

        if options.get("export_image", 0) and not IS_COLAB:
            create_squad_timeline(
                current_squad=data["initial_squad"],
                statistics=result["statistics"],
                picks=result["picks"],
                filename=filename,
            )

    print("Result Summary")
    result_table = pd.DataFrame(response)
    result_table = result_table.sort_values(by="score", ascending=False)
    print(result_table[["iter", "sell", "buy", "chip", "score"]].to_string(index=False))

    if len(options.get("report_decay_base", [])) > 0:
        try:
            print("Decay Metrics")
            metrics_df = pd.DataFrame([{"iter": result["iter"], **result["decay_metrics"]} for result in response])
            print(metrics_df)

            # print("Difference to Best")
            # metrics_diff_df = metrics_df.copy()
            # keys = list(response[0]['decay_metrics'].keys())
            # metrics_diff_df[keys] = metrics_diff_df[keys] - metrics_diff_df[keys].max(axis=0)
            # print(metrics_diff_df)
        except Exception:
            pass

    # Detailed print
    for result in response:
        picks = result["picks"]
        gws = picks["week"].unique()
        print(f"Solution {result['iter'] + 1}")
        for gw in gws:
            chip_text = ""
            line_text = ""
            chip = picks.loc[(picks["week"] == gw) & (picks["chip"] != "")]
            if not chip.empty:
                chip_text = chip.iloc[0]["chip"]
                line_text += f"({chip_text}) "
            sell_text = ", ".join(picks[(picks["week"] == gw) & (picks["transfer_out"] == 1)]["name"].to_list())
            buy_text = ", ".join(picks[(picks["week"] == gw) & (picks["transfer_in"] == 1)]["name"].to_list())

            if sell_text != "" or buy_text != "":
                line_text += sell_text + " -> " + buy_text
            elif chip_text == "FH":
                line_text += ""
            else:
                line_text += "Roll"
            print(f"\tGW{gw}: {line_text}")

        solutions_file = options.get("solutions_file")
        if solutions_file:
            write_line_to_file(solutions_file, result, options)


def write_line_to_file(filename, result, options):
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    gw = min(result["picks"]["week"])
    score = round(result["score"], 3)
    picks = result["picks"]

    cap = picks[(picks["week"] == gw) & (picks["captain"] > BINARY_THRESHOLD)].iloc[0]["id"].astype(int)
    vcap = picks[(picks["week"] == gw) & (picks["vicecaptain"] > BINARY_THRESHOLD)].iloc[0]["id"].astype(int)

    run_id = options["run_id"]
    iteration = result["iter"]
    team_id = options.get("team_id")
    chips = [options.get(x) for x in ["use_wc", "use_bb", "use_fh", "use_tc"]]
    sell_text = ", ".join(picks[(picks["week"] == gw) & (picks["transfer_out"] == 1)]["name"].to_list())
    buy_text = ", ".join(picks[(picks["week"] == gw) & (picks["transfer_in"] == 1)]["name"].to_list())

    headers = [
        "run_id",
        "iter",
        "user_id",
        "wc",
        "bb",
        "fh",
        "tc",
        "cap",
        "vcap",
        "sell",
        "buy",
        "score",
        "datetime",
    ]
    data = [run_id, iteration, team_id, *chips, cap, vcap, sell_text, buy_text, score, t]
    if options.get("show_summary", False):
        headers.append("summary")
        data.append(result["summary"])

    if not os.path.exists(filename):
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(data)

    # Link to FPL.Team
    # get_fplteam_link(options, response)


def get_fplteam_link(options, response):
    print("\nYou can see the solutions on a planner using the following FPL.Team links:")
    team_id = options.get("team_id", 1)
    if options.get("team_id") is None:
        print("(Do not forget to add your team ID to user_settings.json file to get a custom link.)")
    url_base = f"https://fpl.team/plan/{team_id}/?"
    for result in response:
        result_url = url_base
        picks = result["picks"]
        gws = picks["week"].unique()
        for gw in gws:
            lineup_players = ",".join(picks[(picks["week"] == gw) & (picks["lineup"] > BINARY_THRESHOLD)]["id"].astype(str).to_list())
            bench_players = ",".join(picks[(picks["week"] == gw) & (picks["bench"] > -BINARY_THRESHOLD)]["id"].astype(str).to_list())
            cap = picks[(picks["week"] == gw) & (picks["captain"] > BINARY_THRESHOLD)].iloc[0]["id"]
            vcap = picks[(picks["week"] == gw) & (picks["vicecaptain"] > BINARY_THRESHOLD)].iloc[0]["id"]
            chip = picks[picks["week"] == gw].iloc[0]["chip"]
            sold_players = (
                picks[(picks["week"] == gw) & (picks["transfer_out"] > BINARY_THRESHOLD)].sort_values(by="type")["id"].astype(str).to_list()
            )
            bought_players = (
                picks[(picks["week"] == gw) & (picks["transfer_in"] > BINARY_THRESHOLD)].sort_values(by="type")["id"].astype(str).to_list()
            )

            if gw == 1:
                sold_players = []
                bought_players = []

            tr_string = ";".join([f"{i},{j}" for (i, j) in zip(sold_players, bought_players, strict=False)])

            if tr_string == "":
                tr_string = ";"

            sub_text = ""
            if gw == 1:
                sub_text = ";"
            else:
                prev_lineup = (
                    picks[(picks["week"] == gw - 1) & (picks["lineup"] > BINARY_THRESHOLD)].sort_values(by="type")["id"].astype(str).to_list()
                )
                now_bench = picks[(picks["week"] == gw) & (picks["bench"] > -BINARY_THRESHOLD)].sort_values(by="type")["id"].astype(str).to_list()
                lineup_to_bench = [i for i in prev_lineup if i in now_bench]
                prev_bench = (
                    picks[(picks["week"] == gw - 1) & (picks["bench"] > -BINARY_THRESHOLD)].sort_values(by="type")["id"].astype(str).to_list()
                )
                now_lineup = picks[(picks["week"] == gw) & (picks["lineup"] > BINARY_THRESHOLD)].sort_values(by="type")["id"].astype(str).to_list()
                bench_to_lineup = [i for i in prev_bench if i in now_lineup]
                sub_text = ";".join([f"{i},{j}" for (i, j) in zip(lineup_to_bench, bench_to_lineup, strict=False)])

                if sub_text == "":
                    sub_text = ";"

            gw_params = (
                f"lineup{gw}={lineup_players}&bench{gw}={bench_players}&cap{gw}={cap}&vcap{gw}={vcap}"
                f"&chip{gw}={chip}&transfers{gw}={tr_string}&subs{gw}={sub_text}&opt=true"
            )
            result_url += ("" if gw == gws[0] else "&") + gw_params
        print(f"Solution {result['iter'] + 1}: {result_url}")


if __name__ == "__main__":
    solve_regular()
