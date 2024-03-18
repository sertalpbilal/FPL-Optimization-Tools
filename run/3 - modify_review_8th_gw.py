import pandas as pd
import requests
import math
import os


def get_current_event():
    r = requests.get("https://draft.premierleague.com/api/game")
    event_data = r.json()
    return int(event_data["next_event"])


def add_decayed_last_four_gws_to_eight():
    directory = (
        "C:/Users/erknud3/OneDrive - NorgesGruppen/Skrivebord/fpl-optimization/data"
    )
    input_file = os.path.join(directory, "fplreview_12gws.csv")
    output_file = os.path.join(directory, "fplreview.csv")

    gw = get_current_event()
    base_decay = 0.85

    # decay formula is decay base^(n-1)
    decay_9 = math.pow(base_decay, 1)
    decay_10 = math.pow(base_decay, 2)
    decay_11 = math.pow(base_decay, 3)
    decay_12 = math.pow(base_decay, 4)

    # getting the columns name strings
    col_8 = f"{7+gw}_Pts"
    col_9 = f"{8+gw}_Pts"
    col_10 = f"{9+gw}_Pts"
    col_11 = f"{10+gw}_Pts"
    col_12 = f"{11+gw}_Pts"
    c9mins = f"{8+gw}_xMins"
    c10mins = f"{9+gw}_xMins"
    c11mins = f"{10+gw}_xMins"
    c12mins = f"{11+gw}_xMins"

    # Read the CSV file into a pandas DataFrame
    data = pd.read_csv(input_file)

    # Decaying each column and summing them
    data[col_8] = (
        data[col_8]
        + (data[col_9] * decay_9)
        + (data[col_10] * decay_10)
        + (data[col_11] * decay_11)
        + (data[col_12] * decay_12)
    )

    # Dropping the now redundant columns
    data.drop(
        columns=[col_9, c9mins, col_10, c10mins, col_11, c11mins, col_12, c12mins],
        inplace=True,
    )

    # Save the modified data to a new CSV file
    data.to_csv(output_file, index=False)

    print(f"Data decayed at {base_decay} for gw{gw} saved to {output_file}")


if __name__ == "__main__":
    add_decayed_last_four_gws_to_eight()
