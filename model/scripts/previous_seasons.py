import pandas as pd
import numpy as np
import requests
import time
from io import StringIO
from bs4 import BeautifulSoup
import re

url = "https://fbref.com/en/comps/Big5/history/Big-5-European-Leagues-Seasons"
data = requests.get(url)
soup = BeautifulSoup(data.text, "html.parser")
table = soup.find("table", {"id": "seasons"})
table_rows = table.find_all("tr")

desired_seasons = ["2023-2024", "2022-2023", "2021-2022"]
seasons_pattern = "|".join(desired_seasons)

# Debug: Print number of rows found
print(f"Total season rows found: {len(table_rows)}")

# Initialize list for final URLs
season_stats_urls = []

# Process rows to filter and build URLs
for row in table_rows:
    # Find the href attribute of the first <a> tag in the row
    a_tag = row.find("a", href=True)
    if a_tag:
        row_href = a_tag["href"]

        # Check if the href matches any of the desired seasons
        season = re.search(rf"/{seasons_pattern}/", row_href)
        if season:
            print(
                f"Match found for season: {season.group(0)}"
            )  # Debug: Print if match is found

            # Modify the URL to include 'stats/players/' in the correct position
            modified_href = re.sub(r"(/[^/]+)$", r"/stats/players\1", row_href)
            full_url = f"https://fbref.com{modified_href}"
            season_stats_urls.append(full_url)

            print(f"Final URL: {full_url}")  # Debug: Print each final URL

            time.sleep(
                3
            )  # Optional: Delay between requests to avoid overloading the server

# Debug: Print number of final URLs
print(f"Total season stats URLs: {len(season_stats_urls)}")
# Debug: Print all final URLs before extraction
print(f"All season stats URLs: {len(season_stats_urls)}\n{season_stats_urls}")

# Extend the list with other leagues and seasons
season_stats_urls.extend(
    [
        "https://fbref.com/en/comps/10/2023-2024/stats/2023-2024-Championship-Stats",
        "https://fbref.com/en/comps/10/2022-2023/stats/2022-2023-Championship-Stats",
        "https://fbref.com/en/comps/10/2021-2022/stats/2021-2022-Championship-Stats",
        "https://fbref.com/en/comps/23/2023-2024/stats/2023-2024-Eredivisie-Stats",
        "https://fbref.com/en/comps/23/2022-2023/stats/2022-2023-Eredivisie-Stats",
        "https://fbref.com/en/comps/23/2021-2022/stats/2021-2022-Eredivisie-Stats",
        "https://fbref.com/en/comps/32/2023-2024/stats/2023-2024-Primeira-Liga-Stats",
        "https://fbref.com/en/comps/32/2022-2023/stats/2022-2023-Primeira-Liga-Stats",
        "https://fbref.com/en/comps/32/2021-2022/stats/2021-2022-Primeira-Liga-Stats",
    ]
)


def extract_data_from_url(index, url):
    try:
        data = requests.get(url).text.replace("<!--", "").replace("-->", "")
        soup = BeautifulSoup(data, "html.parser")
        season = re.search(r"/(\d{4}-\d{4})/", url).group(1)

        if index >= 3:
            h2_element = soup.find("h2")
            competition = (
                h2_element.find("span").get_text().split()[-1]
                if h2_element and h2_element.find("span")
                else pd.NA
            )
        else:
            competition = pd.NA

        table = soup.find("table", {"id": "stats_standard"})
        ids = [
            x["data-append-csv"] for x in table.find_all("td", {"data-stat": "player"})
        ]

        df = pd.read_html(StringIO(str(table)))[0]
        df.columns = [f"{i} {j}" if "Unnamed" not in i else j for i, j in df.columns]
        df = df[df["Rk"] != "Rk"]
        df["Fbref"] = ids
        df["Season"] = season
        df["Competition"] = competition

        if "Comp" not in df.columns:
            df["Comp"] = pd.NA

        cols_to_move = ["Fbref", "Season", "Competition"]
        remaining_cols = [col for col in df.columns if col not in cols_to_move]
        df = df[remaining_cols[:1] + cols_to_move + remaining_cols[1:]]
        df = df.rename(
            {
                "Playing Time MP": "MP",
                "Playing Time Starts": "Starts",
                "Playing Time Min": "Min",
                "Playing Time 90s": "90s",
                "Performance G-PK": "Total_npG",
                "Expected npxG": "Total_npxG",
                "Per 90 Minutes npxG": "npxG",
                "Per 90 Minutes xAG": "xAG",
            },
            axis=1,
        )

        return df

    except Exception as e:
        print(f"An error occurred for URL index {index}: {e}")
        return pd.DataFrame()


def weighted_avg_with_recency_and_multiplier(
    values, weights, comps, recency_weights, multipliers
):
    multipliers_series = pd.Series(
        [multipliers.get(comp, 1) for comp in comps], index=weights.index
    )
    adjusted_values = values * multipliers_series
    adjusted_weights = weights * recency_weights
    total_weight = np.sum(adjusted_weights)
    return (
        np.sum(adjusted_values * adjusted_weights) / total_weight
        if total_weight > 0
        else np.nan
    )


def calculate_recency_weights(df):
    def recency_weights(seasons):
        unique_seasons = sorted(seasons.unique(), reverse=True)
        num_seasons = len(unique_seasons)
        weights = {season: num_seasons - i for i, season in enumerate(unique_seasons)}
        return seasons.map(weights)

    # Use .copy() to avoid the SettingWithCopyWarning
    df = df.copy()
    df["recency_weight"] = df.groupby("Squad")["Season"].transform(recency_weights)
    return df["recency_weight"]


def process_dataframes(all_dfs):
    all_players_prev_seasons = pd.concat(all_dfs)
    all_players_prev_seasons = all_players_prev_seasons[
        [
            "Fbref",
            "Season",
            "Player",
            "Squad",
            "Competition",
            "Comp",
            "Age",
            "MP",
            "Starts",
            "Min",
            "90s",
            "Total_npG",
            "Total_npxG",
            "npxG",
            "xAG",
        ]
    ]
    all_players_prev_seasons = all_players_prev_seasons.astype(
        {
            "MP": "int",
            "Starts": "int",
            "Min": "int",
            "90s": "float64",
            "Total_npG": "int",
            "Total_npxG": "float64",
            "npxG": "float64",
            "xAG": "float64",
        }
    )
    all_players_prev_seasons["Comp"] = (
        all_players_prev_seasons["Comp"].str.split(" ", n=1).str[1]
    )
    all_players_prev_seasons["Comp"] = all_players_prev_seasons["Comp"].fillna(
        all_players_prev_seasons["Competition"]
    )
    all_players_prev_seasons = all_players_prev_seasons.drop(columns=["Competition"])

    finishing_df = all_players_prev_seasons[
        ["Fbref", "Season", "Player", "Squad", "Comp", "Total_npG", "Total_npxG"]
    ].copy()

    finishing_df = (
        finishing_df.groupby(["Fbref", "Player"])
        .agg(Total_npG=("Total_npG", "sum"), Total_npxG=("Total_npxG", "sum"))
        .reset_index()
    )

    finishing_df["finishing"] = (
        (finishing_df["Total_npG"] + 55) / (finishing_df["Total_npxG"] + 55)
    ).round(2)

    all_players_prev_seasons = (
        all_players_prev_seasons.groupby(
            ["Fbref", "Season", "Player", "Squad", "Comp", "Age"]
        )
        .agg(
            MP=("MP", "sum"),
            Starts=("Starts", "sum"),
            Min=("Min", "sum"),
            ninetys=("90s", "sum"),
            npxG=(
                "npxG",
                lambda x: (
                    (x * all_players_prev_seasons.loc[x.index, "90s"]).sum()
                    / all_players_prev_seasons.loc[x.index, "90s"].sum()
                    if all_players_prev_seasons.loc[x.index, "90s"].sum() > 0
                    else 0
                ),
            ),
            xAG=(
                "xAG",
                lambda x: (
                    (x * all_players_prev_seasons.loc[x.index, "90s"]).sum()
                    / all_players_prev_seasons.loc[x.index, "90s"].sum()
                    if all_players_prev_seasons.loc[x.index, "90s"].sum() > 0
                    else 0
                ),
            ),
        )
        .reset_index()
    )

    all_players_prev_seasons = all_players_prev_seasons.rename(
        columns={"ninetys": "90s"}
    )
    all_players_prev_seasons["recency_weight"] = calculate_recency_weights(
        all_players_prev_seasons
    )

    multipliers = {
        "Premier League": 1,
        "Ligue 1": 0.75,
        "Serie A": 0.75,
        "Bundesliga": 0.75,
        "La Liga": 0.75,
        "Primeira Liga": 0.5,
        "Championship": 0.5,
        "Eredivisie": 0.5,
    }

    all_players_prev_seasons = (
        all_players_prev_seasons.groupby(["Fbref", "Player"])
        .agg(
            Age=("Age", "max"),
            Seasons_count=("Season", "nunique"),
            MP=("MP", "sum"),
            Starts=("Starts", "sum"),
            Min=("Min", "sum"),
            ninetys=("90s", "sum"),
            npxG=(
                "npxG",
                lambda x: weighted_avg_with_recency_and_multiplier(
                    x,
                    all_players_prev_seasons.loc[x.index, "90s"],
                    all_players_prev_seasons.loc[x.index, "Comp"],
                    all_players_prev_seasons.loc[x.index, "recency_weight"],
                    multipliers,
                ),
            ),
            xAG=(
                "xAG",
                lambda x: weighted_avg_with_recency_and_multiplier(
                    x,
                    all_players_prev_seasons.loc[x.index, "90s"],
                    all_players_prev_seasons.loc[x.index, "Comp"],
                    all_players_prev_seasons.loc[x.index, "recency_weight"],
                    multipliers,
                ),
            ),
        )
        .reset_index()
    )

    all_players_prev_seasons = all_players_prev_seasons.rename(
        columns={"ninetys": "90s"}
    )
    all_players_prev_seasons[["npxG", "xAG"]] = all_players_prev_seasons[
        ["npxG", "xAG"]
    ].round(2)

    all_players_prev_seasons = all_players_prev_seasons.merge(
        finishing_df[["Fbref", "finishing"]], on="Fbref", how="inner"
    )

    return all_players_prev_seasons, finishing_df


def main():
    # Initialize the list to store DataFrames
    all_dfs = []

    # Debug: Print all final URLs before extraction
    print(f"All season stats URLs: {len(season_stats_urls)}\n{season_stats_urls}")

    # Process each URL
    for index, url in enumerate(season_stats_urls):
        df = extract_data_from_url(index, url)
        if not df.empty:
            all_dfs.append(df)
            print(f"Data successfully extracted for URL index {index}")
        else:
            print(f"Empty DataFrame for URL index {index}")

        time.sleep(3)  # Pause to avoid being blocked by the server

    # Combine all DataFrames and process them
    if all_dfs:
        all_players_prev_seasons, finishing_df = process_dataframes(all_dfs)
        print("Data processing complete.")
        print(all_players_prev_seasons.sort_values(by="npxG", ascending=False).head(10))

        # Save the DataFrame to a CSV file
        csv_file_path = "C:/Users/erknud3/fpl-optimization/model/data/Historic_Data"
        all_players_prev_seasons.to_csv(
            f"{csv_file_path}/all_players_prev_seasons.csv", index=False
        )
        print(f"Data saved to {csv_file_path}/all_players_prev_seasons.csv")

        finishing_df.to_csv(f"{csv_file_path}/finishing_df.csv", index=False)
        print(f"Data saved to {csv_file_path}/finishing_df.csv")
    else:
        print("No dataframes were extracted.")


if __name__ == "__main__":
    main()
