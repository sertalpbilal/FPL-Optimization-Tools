import pandas as pd
import os

filename = (input("What CSV are you inspecting? "))
filepath = os.path.join("data", "results", filename)
picks = pd.read_csv(filepath)

def print_transfers(picks):
    gws = picks['week'].unique()
    for gw in gws:
        line_text = ''
        chip_text = picks[picks['week']==gw].fillna("").iloc[0]['chip']
        if chip_text != '':
            line_text += '(' + chip_text + ') '
        sell_text = ', '.join(picks[(picks['week'] == gw) & (picks['transfer_out'] == 1)]['name'].to_list())
        buy_text = ', '.join(picks[(picks['week'] == gw) & (picks['transfer_in'] == 1)]['name'].to_list())
        if sell_text != '':
            line_text += sell_text + ' -> ' + buy_text
        else:
            line_text += "Roll"
        print(f"  GW{gw}: {line_text}")


def print_lineups(picks):
    gws = picks['week'].unique()
    summary_of_actions = ""
    move_summary = {'chip': [], 'buy': [], 'sell': []}
    cumulative_xpts = 0
    for gw in gws:
        summary_of_actions += f"** GW {gw}:\n"
        chip = picks[picks['week']==gw].fillna("").iloc[0]['chip']
        if chip != "":
            summary_of_actions += "CHIP " + chip + "\n"
            move_summary['chip'].append(chip + str(gw))
        
        t_in = picks.loc[(picks['week'] == gw) & (picks['transfer_in'] == 1)][['name', 'id']].values
        t_out = picks.loc[(picks['week'] == gw) & (picks['transfer_out'] == 1)][['name', 'id']].values
        
        for name, fpl_id in t_in:
            summary_of_actions += f"Buy {fpl_id} - {name}\n"
        for name, fpl_id in t_out:
            summary_of_actions += f"Sell {fpl_id} - {name}\n"

        lineup_players = picks[(picks['week'] == gw) & (picks['lineup'] == 1)]
        bench_players = picks[(picks['week'] == gw) & (picks['bench'] >= 0)]
        
        summary_of_actions += "---\nLineup: \n"

        def get_display(row):
            return f"{row['name']} ({row['xP']}{', C' if row['captain'] == 1 else ''}{', V' if row['vicecaptain'] == 1 else ''})"

        for type in [1,2,3,4]:
            type_players = lineup_players[lineup_players['type'] == type]
            entries = type_players.apply(get_display, axis=1)
            summary_of_actions += '\t' + ', '.join(entries.tolist()) + "\n"
        summary_of_actions += "Bench: \n\t" + ', '.join(bench_players['name'].tolist()) + "\n"
        summary_of_actions += "Lineup xPts: " + str(round(lineup_players['xp_cont'].sum(),2)) + "\n---\n\n"
        cumulative_xpts = cumulative_xpts + round(lineup_players['xp_cont'].sum(),2)

    print(summary_of_actions)
    print("Cumulative xPts: " + str(round(cumulative_xpts,2)) + "\n---\n\n")


print_lineups(picks)
print_transfers(picks)