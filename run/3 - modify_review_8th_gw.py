import pandas as pd
import requests
import math
import os
import sqlite3
from datetime import datetime


def get_current_event():
    r = requests.get("https://draft.premierleague.com/api/game")
    event_data = r.json()
    return int(event_data["next_event"])


def add_decayed_last_four_gws_to_eight():
    directory = "C:/Users/erknud3/fpl-optimization/data"
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

    relevant_players = pd.read_csv(
        "C:/Users/erknud3/fpl-optimization/data/relevant_players_wc6.csv"
    )

    data = data.merge(relevant_players[["ID"]], on="ID", how="inner")

    # Save the modified data to a new CSV file
    data.to_csv(output_file, index=False)

    print(f"Data decayed at {base_decay} for gw{gw} saved to {output_file}")

    # Add a new column with the current timestamp
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["created_dt"] = current_time

    conn = sqlite3.connect("C:/Users/erknud3/fpl-optimization/model/FBRef_DB/master.db")
    cursor = conn.cursor()

    # Table name
    table_name = "fplreview"

    # Check if the table exists
    cursor.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';"
    )
    table_exists = cursor.fetchone()

    if table_exists:
        # If the table exists, truncate (delete all rows)
        cursor.execute(f"DELETE FROM {table_name};")
        print(f"Table '{table_name}' found. Truncating table...")

        # Insert data into the table
        data.to_sql(table_name, conn, if_exists="append", index=False)
        print(f"Data inserted into table '{table_name}'.")
    else:
        # If the table does not exist, create it and insert data
        print(f"Table '{table_name}' not found. Creating table and inserting data...")
        data.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"Table '{table_name}' created and data inserted.")

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()


if __name__ == "__main__":
    add_decayed_last_four_gws_to_eight()
