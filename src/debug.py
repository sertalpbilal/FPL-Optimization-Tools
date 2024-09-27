import pandas as pd
import numpy as np
from data_parser import read_data
import requests
import sasoptpy as so


datasource = "garz"
data_weights = None

options = {
    "horizon": 3,
    "randomized": False,
    "wc_limit": 0,
    "banned": [],
    "xmin_lb": 0,
}

r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
fpl_data = r.json()

gw = 0
for e in fpl_data["events"]:
    if e["is_next"]:
        gw = e["id"]
        break

horizon = options.get("horizon", 3)

element_data = pd.DataFrame(fpl_data["elements"])
element_data = element_data[
    ["id", "element_type", "now_cost", "team", "team_code", "web_name"]
]
team_data = pd.DataFrame(fpl_data["teams"])
team_data = team_data[["id", "name", "code"]]
elements_team = pd.merge(element_data, team_data, left_on="team", right_on="id")

data = read_data(options, datasource, data_weights)

data = data.fillna(0)
if "ID" in data:
    data["review_id"] = data["ID"]
    print("Using ID")
else:
    data["review_id"] = data.index + 1
    print("Using index")

if options.get("export_data", "") != "" and datasource == "mixed":
    data.to_csv(f"../data/{options['export_data']}")

merged_data = pd.merge(elements_team, data, left_on="id_x", right_on="review_id")
merged_data = merged_data[
    [
        "id_x",
        "web_name",
        "element_type",
        "now_cost",
        "id_y",
        "review_id",
        "Team",
        "4_Pts",
    ]
]
merged_data.set_index(["id_x"], inplace=True)

# Check if data exists
for week in range(gw, min(39, gw + horizon)):
    if f"{week}_Pts" not in data.keys():
        raise ValueError(
            f"{week}_Pts is not inside prediction data, change your horizon parameter or update your prediction data"
        )

original_keys = merged_data.columns.to_list()
keys = [k for k in original_keys if "_Pts" in k]
min_keys = [k for k in original_keys if "_xMins" in k]
merged_data["total_ev"] = merged_data[keys].sum(axis=1)
merged_data["total_min"] = merged_data[min_keys].sum(axis=1)

merged_data.sort_values(by=["total_ev"], ascending=[False], inplace=True)

players = merged_data.index.to_list()
type_data = pd.DataFrame(fpl_data["element_types"]).set_index(["id"])
element_types = type_data.index.to_list()

# Fixture info
team_code_dict = team_data.set_index("id")["name"].to_dict()
fixture_data = requests.get("https://fantasy.premierleague.com/api/fixtures/").json()
fixtures = [
    {
        "gw": f["event"],
        "home": team_code_dict[f["team_h"]],
        "away": team_code_dict[f["team_a"]],
    }
    for f in fixture_data
]

next_gw = 4
teams = team_data["name"].to_list()
last_gw = next_gw + horizon - 1
if last_gw > 38:
    last_gw = 38
    horizon = 39 - next_gw
gameweeks = list(range(next_gw, last_gw + 1))
all_gw = [next_gw - 1] + gameweeks
order = [0, 1, 2, 3]
ft_states = [0, 1, 2, 3, 4, 5]

objective = "regular"
problem_name = (
    f"mp_h{horizon}_regular"
    if objective == "regular"
    else f"mp_h{horizon}_o{objective[0]}_d{decay_base}"
)

model = so.Model(name=problem_name)

squad = model.add_variables(players, all_gw, name="squad", vartype=so.binary)
squad_fh = model.add_variables(players, gameweeks, name="squad_fh", vartype=so.binary)
lineup = model.add_variables(players, gameweeks, name="lineup", vartype=so.binary)
captain = model.add_variables(players, gameweeks, name="captain", vartype=so.binary)
vicecap = model.add_variables(players, gameweeks, name="vicecap", vartype=so.binary)
bench = model.add_variables(players, gameweeks, order, name="bench", vartype=so.binary)

lineup_type_count = {
    (t, w): so.expr_sum(
        lineup[p, w] for p in players if merged_data.loc[p, "element_type"] == t
    )
    for t in element_types
    for w in gameweeks
}

squad_type_count = {
    (t, w): so.expr_sum(
        squad[p, w] for p in players if merged_data.loc[p, "element_type"] == t
    )
    for t in element_types
    for w in gameweeks
}

points_player_week = {
    (p, w): merged_data.loc[p, f"{w}_Pts"] for p in players for w in gameweeks
}
