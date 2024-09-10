import pandas as pd
import numpy as np
from data_parser import read_data
import requests


datasource = "garz"
data_weights = None

options = {
    "horizon": 3,
    "randomized": False,
    "wc_limit": 0,
    "banned": [],
    "xmin_lb": 0,
}

data = read_data(options, datasource, weights=None)

r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
players = r.json()["elements"]
existing_ids = data["review_id"].tolist()
element_type_dict = {1: "G", 2: "D", 3: "M", 4: "F"}
teams = r.json()["teams"]
team_code_dict = {i["code"]: i for i in teams}
missing_players = []
for p in players:
    if p["id"] in existing_ids:
        continue
    missing_players.append(
        {
            "fpl_id": p["id"],
            "review_id": p["id"],
            "ID": p["id"],
            "real_id": p["id"],
            "team": "",
            "Name": p["web_name"],
            "Pos": element_type_dict[p["element_type"]],
            "Value": p["now_cost"] / 10,
            "Team": team_code_dict[p["team_code"]]["name"],
            "Missing": 1,
        }
    )
garz_data = pd.concat([data, pd.DataFrame(missing_players)]).fillna(0)


def calculate_fts(transfers, next_gw, fh, wc_gws):
    n_transfers = {gw: 0 for gw in range(2, next_gw)}
    for t in transfers:
        n_transfers[t["event"]] += 1
    fts = {gw: 0 for gw in range(2, next_gw + 1)}
    fts[2] = 1
    for i in range(3, next_gw + 1):
        if (i - 1) == fh:
            fts[i] = fts[i - 1]
            continue
        if i - 1 in wc_gws:
            fts[i] = fts[i - 1]
            continue
        fts[i] = fts[i - 1]
        fts[i] -= n_transfers[i - 1]
        fts[i] = max(fts[i], 0)
        fts[i] += 1
        fts[i] = min(fts[i], 5)
    return fts[next_gw]


team_id = 487

BASE_URL = "https://fantasy.premierleague.com/api"
with requests.Session() as session:
    static_url = f"{BASE_URL}/bootstrap-static/"
    static = session.get(static_url).json()
    next_gw = [x for x in static["events"] if x["is_next"]][0]["id"]

    start_prices = {
        x["id"]: x["now_cost"] - x["cost_change_start"] for x in static["elements"]
    }
    gw1_url = f"{BASE_URL}/entry/{team_id}/event/1/picks/"
    gw1 = session.get(gw1_url).json()

    transfers_url = f"{BASE_URL}/entry/{team_id}/transfers/"
    transfers = session.get(transfers_url).json()[::-1]

    chips_url = f"{BASE_URL}/entry/{team_id}/history/"
    chips = session.get(chips_url).json()["chips"]
    fh = [x for x in chips if x["name"] == "freehit"]
    if fh:
        fh = fh[0]["event"]
    wc_gws = [x["event"] for x in chips if x["name"] == "wildcard"]

# squad will remain an ID:puchase_price map throughout iteration over transfers
# once they have been iterated through, can then add on the current selling price
squad = {x["element"]: start_prices[x["element"]] for x in gw1["picks"]}

itb = 1000 - sum(squad.values())
for t in transfers:
    if t["event"] == fh:
        continue
    itb += t["element_out_cost"]
    itb -= t["element_in_cost"]
    del squad[t["element_out"]]
    squad[t["element_in"]] = t["element_in_cost"]

fts = calculate_fts(transfers, next_gw, fh, wc_gws)
my_data = {
    "chips": [],
    "picks": [],
    "team_id": team_id,
    "transfers": {
        "bank": itb,
        "limit": fts,
        "made": 0,
    },
}
for player_id, purchase_price in squad.items():
    now_cost = [x for x in static["elements"] if x["id"] == player_id][0]["now_cost"]

    diff = now_cost - purchase_price
    if diff > 0:
        selling_price = purchase_price + diff // 2
    else:
        selling_price = now_cost

    my_data["picks"].append(
        {
            "element": player_id,
            "purchase_price": purchase_price,
            "selling_price": selling_price,
        }
    )

buy_price = (data["Value"] / 10).to_dict()
sell_price = {i["element"]: i["selling_price"] / 10 for i in my_data["picks"]}

price_modified_players = []

preseason = options.get("preseason", False)
if not preseason:
    for i in my_data["picks"]:
        if purchase_price[i["element"]] != selling_price[i["element"]]:
            price_modified_players.append(i["element"])
            print(
                f"Added player {i['element']} to list, buy price {purchase_price[i['element']]} sell price {selling_price[i['element']]}"
            )
