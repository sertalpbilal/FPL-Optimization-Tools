import pandas as pd
from pathlib import Path
import sys
import argparse


def read_sensitivity(options=None):

    if options is None or options.get("gw") is None:
        gw = int(input("What GW are you assessing? "))
        situation = input("Is this a wildcard or preseason (GW1) solve? (y/n) ")
    else:
        gw = options["gw"]
        situation = options.get("situation", "n")

    print()

    directory = "../data/results/sakalocked"
    # no_plans = len(os.listdir(directory))

    if situation == "N" or situation == "n":

        buys = []
        sells = []
        no_plans = 0

        for filename in Path(directory).glob("*.csv"):
            plan = pd.read_csv(filename)
            if (
                plan[(plan["week"] == gw) & (plan["transfer_in"] == 1)][
                    "name"
                ].to_list()
                == []
            ):
                buys += ["No transfer"]
                sells += ["No transfer"]
            else:
                buy_list = plan[(plan["week"] == gw) & (plan["transfer_in"] == 1)][
                    "name"
                ].to_list()
                buy = ", ".join(buy_list)
                buys.append(buy)

                sell_list = plan[(plan["week"] == gw) & (plan["transfer_out"] == 1)][
                    "name"
                ].to_list()
                sell = ", ".join(sell_list)
                sells.append(sell)
            no_plans += 1

        buy_sum = (
            pd.DataFrame(buys, columns=["player"])
            .value_counts()
            .reset_index(name="PSB")
        )
        sell_sum = (
            pd.DataFrame(sells, columns=["player"])
            .value_counts()
            .reset_index(name="PSB")
        )

        buy_sum["PSB"] = [
            "{:.0%}".format(buy_sum["PSB"][x] / no_plans)
            for x in range(buy_sum.shape[0])
        ]
        sell_sum["PSB"] = [
            "{:.0%}".format(sell_sum["PSB"][x] / no_plans)
            for x in range(sell_sum.shape[0])
        ]

        print("Buy:")
        print("\n".join(buy_sum.to_string(index=False).split("\n")[1:]))
        print()
        print("Sell:")
        print("\n".join(sell_sum.to_string(index=False).split("\n")[1:]))
        print()

    elif situation == "Y" or situation == "y":

        goalkeepers = []
        defenders = []
        midfielders = []
        forwards = []

        no_plans = 0

        for filename in Path(directory).glob("*.csv"):
            plan = pd.read_csv(filename)
            goalkeepers += plan[
                (plan["week"] == gw)
                & (plan["pos"] == "GKP")
                & (plan["transfer_out"] != 1)
            ]["name"].to_list()
            defenders += plan[
                (plan["week"] == gw)
                & (plan["pos"] == "DEF")
                & (plan["transfer_out"] != 1)
            ]["name"].to_list()
            midfielders += plan[
                (plan["week"] == gw)
                & (plan["pos"] == "MID")
                & (plan["transfer_out"] != 1)
            ]["name"].to_list()
            forwards += plan[
                (plan["week"] == gw)
                & (plan["pos"] == "FWD")
                & (plan["transfer_out"] != 1)
            ]["name"].to_list()
            no_plans += 1

        keepers = (
            pd.DataFrame(goalkeepers, columns=["player"])
            .value_counts()
            .reset_index(name="PSB")
        )
        defs = (
            pd.DataFrame(defenders, columns=["player"])
            .value_counts()
            .reset_index(name="PSB")
        )
        mids = (
            pd.DataFrame(midfielders, columns=["player"])
            .value_counts()
            .reset_index(name="PSB")
        )
        fwds = (
            pd.DataFrame(forwards, columns=["player"])
            .value_counts()
            .reset_index(name="PSB")
        )

        keepers["PSB"] = [
            "{:.0%}".format(keepers["PSB"][x] / no_plans)
            for x in range(keepers.shape[0])
        ]
        defs["PSB"] = [
            "{:.0%}".format(defs["PSB"][x] / no_plans) for x in range(defs.shape[0])
        ]
        mids["PSB"] = [
            "{:.0%}".format(mids["PSB"][x] / no_plans) for x in range(mids.shape[0])
        ]
        fwds["PSB"] = [
            "{:.0%}".format(fwds["PSB"][x] / no_plans) for x in range(fwds.shape[0])
        ]

        print("Goalkeepers:")
        print("\n".join(keepers.to_string(index=False).split("\n")[1:]))
        print()
        print("Defenders:")
        print("\n".join(defs.to_string(index=False).split("\n")[1:]))
        print()
        print("Midfielders:")
        print("\n".join(mids.to_string(index=False).split("\n")[1:]))
        print()
        print("Forwards:")
        print("\n".join(fwds.to_string(index=False).split("\n")[1:]))

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
