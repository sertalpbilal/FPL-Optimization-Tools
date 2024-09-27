import sqlite3
import pandas as pd
import numpy as np

# Connect to the SQLite database
conn = sqlite3.connect("C:/Users/erknud3/fpl-optimization/model/FBRef_DB/master.db")

print("Loading data from the database...")

# Load data from Match table
match_df = pd.read_sql_query(
    """
    SELECT *
    FROM Match
    WHERE competition IN ('Premier_League', 'Championship')
    """,
    conn,
)

# Load data from Player_Info and Summary
player_info_df = pd.read_sql_query(
    """
    SELECT b.*
    FROM Player_Info b
    JOIN Match a ON a.match_id = b.match_id
    WHERE a.competition IN ('Premier_League', 'Championship')
    """,
    conn,
)

summary_df = pd.read_sql_query(
    """
    SELECT c.*
    FROM Summary c
    JOIN Match a ON a.match_id = c.match_id
    WHERE a.competition IN ('Premier_League', 'Championship')
    """,
    conn,
)

# Close the connection
conn.close()

print("Merging data...")

# Merge the DataFrames
merged_df = pd.merge(
    player_info_df, summary_df, on=["match_id", "player_id"], how="inner"
)
merged_df = pd.merge(merged_df, match_df, on="match_id", how="inner")

# Calculate 'team' and 'opponent' columns
merged_df["team"] = merged_df.apply(
    lambda row: row["home_team"] if row["home_away"] == "H" else row["away_team"],
    axis=1,
)
merged_df["opponent"] = merged_df.apply(
    lambda row: row["away_team"] if row["home_away"] == "H" else row["home_team"],
    axis=1,
)

# Precompute xG and xGC
merged_df["team_xG"] = np.where(
    merged_df["home_away"] == "H", merged_df["home_xG"], merged_df["away_xG"]
)
merged_df["team_xGC"] = np.where(
    merged_df["home_away"] == "H", merged_df["away_xG"], merged_df["home_xG"]
)

print("Calculating penalties...")

# Calculate total penalties attempted for each team and opponent
team_penalties = (
    merged_df.groupby(["match_id", "team"])["penalties_attempted"].sum().reset_index()
)
team_penalties = team_penalties.rename(
    columns={"penalties_attempted": "team_penalties_attempted"}
)

opponent_penalties = (
    merged_df.groupby(["match_id", "opponent"])["penalties_attempted"]
    .sum()
    .reset_index()
)
opponent_penalties = opponent_penalties.rename(
    columns={"penalties_attempted": "opponent_penalties_attempted", "opponent": "team"}
)

# Merge penalties data back to the original dataframe
merged_df = merged_df.merge(team_penalties, on=["match_id", "team"], how="left")
merged_df = merged_df.merge(opponent_penalties, on=["match_id", "team"], how="left")

# Ensure no null values in merged penalties columns
merged_df["team_penalties_attempted"] = merged_df["team_penalties_attempted"].fillna(0)
merged_df["opponent_penalties_attempted"] = merged_df[
    "opponent_penalties_attempted"
].fillna(0)

print("Grouping and calculating statistics...")

# Group by necessary columns to get one row per match and team
grouped_df = (
    merged_df.groupby(["competition", "season", "date", "match_id", "team", "opponent"])
    .agg(
        xG=("team_xG", "first"),  # xG for the team
        penalties_attempted=(
            "team_penalties_attempted",
            "first",
        ),  # Team penalties attempted
        xGC=("team_xGC", "first"),  # xGC for the team
        penalties_conceded=(
            "opponent_penalties_attempted",
            "first",
        ),  # Penalties conceded
    )
    .reset_index()
)

# Ensure correct mirroring of penalties_conceded
grouped_df["penalties_conceded"] = grouped_df.apply(
    lambda row: (
        grouped_df.loc[
            (grouped_df["match_id"] == row["match_id"])
            & (grouped_df["team"] == row["opponent"]),
            "penalties_attempted",
        ].values[0]
        if not grouped_df.loc[
            (grouped_df["match_id"] == row["match_id"])
            & (grouped_df["team"] == row["opponent"]),
            "penalties_attempted",
        ].empty
        else 0
    ),
    axis=1,
)

# Calculate non-penalty xG (npxG) and xGC (npxGC)
grouped_df["npxG"] = grouped_df["xG"] - (grouped_df["penalties_attempted"] * 0.77)
grouped_df["npxGC"] = grouped_df["xGC"] - (grouped_df["penalties_conceded"] * 0.77)

# Group by competition, season, and team to calculate stats per 90 minutes
team_stats_df = (
    grouped_df.groupby(["competition", "season", "team"])
    .agg(
        total_npxG=("npxG", "sum"),
        total_npxGC=("npxGC", "sum"),
        total_matches=("match_id", "count"),  # Total number of matches played
    )
    .reset_index()
)

# Calculate npxG/90 and npxGC/90 for each team
team_stats_df["npxG/90"] = round(
    team_stats_df["total_npxG"] / team_stats_df["total_matches"], 2
)
team_stats_df["npxGC/90"] = round(
    team_stats_df["total_npxGC"] / team_stats_df["total_matches"], 2
)

print("Creating final DataFrame...")


# Adjust `npxG/90` and `npxGC/90` for prior seasons
def adjust_for_championship(row):
    if row["competition"] == "Championship":
        row["npxG/90"] *= 0.5
        row["npxGC/90"] *= 2
    return row


# Apply adjustment for Championship teams
team_stats_df = team_stats_df.apply(adjust_for_championship, axis=1)

# Filter for Premier League teams in the current season
current_season = "2024-2025"
premier_league_teams = team_stats_df[
    (team_stats_df["season"] == current_season)
    & (team_stats_df["competition"] == "Premier_League")
]["team"]


# Compute weighted prior baselines
def compute_prior_beliefs(df, team, seasons):
    weights = {"2023-2024": 0.7, "2022-2023": 0.2, "2021-2022": 0.1}
    total_weight = 38
    prior_npxG = 0
    prior_npxGC = 0
    total_prior_matches = 0

    for season in seasons:
        team_data = df[(df["season"] == season) & (df["team"] == team)]
        if not team_data.empty:
            weight = weights.get(season, 0)
            prior_npxG += np.round(team_data["npxG/90"].values[0] * weight, 2)
            prior_npxGC += np.round(team_data["npxGC/90"].values[0] * weight, 2)
            total_prior_matches += weight * total_weight

    return prior_npxG, prior_npxGC, total_prior_matches


# Initialize results list
results = []

for team in premier_league_teams:
    # Compute prior beliefs
    prior_npxG, prior_npxGC, total_prior_matches = compute_prior_beliefs(
        team_stats_df, team, ["2023-2024", "2022-2023", "2021-2022"]
    )

    # Extract current season data
    current_season_data = team_stats_df[
        (team_stats_df["season"] == current_season) & (team_stats_df["team"] == team)
    ]

    if not current_season_data.empty:
        current_npxG = current_season_data["npxG/90"].values[0]
        current_npxGC = current_season_data["npxGC/90"].values[0]
        current_total_matches = current_season_data["total_matches"].values[0]

        # Weight for the current season
        weight_current_season = current_total_matches * 1.5
        weight_prior = total_prior_matches

        # Calculate final weighted averages
        final_npxG = np.round(
            (prior_npxG * weight_prior + current_npxG * weight_current_season)
            / (weight_prior + weight_current_season),
            2,
        )
        final_npxGC = np.round(
            (prior_npxGC * weight_prior + current_npxGC * weight_current_season)
            / (weight_prior + weight_current_season),
            2,
        )

        results.append(
            {
                "team": team,
                "prior_npxG": prior_npxG,
                "prior_npxGC": prior_npxGC,
                "current_npxG": current_npxG,
                "current_npxGC": current_npxGC,
                "npxG_baseline": final_npxG,
                "npxGC_baseline": final_npxGC,
            }
        )

# Convert results to DataFrame
final_df = pd.DataFrame(results)
final_df["team_id"] = final_df.index + 1
final_df = final_df[
    [
        "team_id",
        "team",
        "prior_npxG",
        "current_npxG",
        "npxG_baseline",
        "prior_npxGC",
        "current_npxGC",
        "npxGC_baseline",
    ]
]

# Print final_df
# print(final_df)

# Connect to the SQLite database
conn = sqlite3.connect("C:/Users/erknud3/fpl-optimization/model/FBRef_DB/master.db")
cursor = conn.cursor()

# Table name
table_name = "team_baselines"

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
    final_df.to_sql(table_name, conn, if_exists="append", index=False)
    print(f"Data inserted into table '{table_name}'.")
else:
    # If the table does not exist, create it and insert data
    print(f"Table '{table_name}' not found. Creating table and inserting data...")
    final_df.to_sql(table_name, conn, if_exists="replace", index=False)
    print(f"Table '{table_name}' created and data inserted.")

# Commit the transaction and close the connection
conn.commit()
conn.close()

# # Save to CSV
# final_df.to_csv(
#     "C:/Users/erknud3/fpl-optimization/model/data//team_baselines.csv", index=False
# )

# print("Data saved to 'team_baselines.csv'.")
