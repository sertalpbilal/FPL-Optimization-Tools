import pandas as pd
import requests
import time
from io import StringIO
from bs4 import BeautifulSoup
import re


def generate_season_stats_urls(desired_seasons):
    desired_seasons = ["2023-2024", "2022-2023", "2021-2022"]

    base_urls = [
        "https://fbref.com/en/comps/9/history/Premier-League-Seasons",  # Premier League
        "https://fbref.com/en/comps/10/history/Championship-Seasons",  # Championship
    ]

    season_stats_urls = []
    seasons_pattern = "|".join(desired_seasons)

    with requests.Session() as session:
        for base_url in base_urls:
            response = session.get(base_url)
            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", {"id": "seasons"})
            table_rows = table.find_all("tr")

            print(f"Total season rows found for {base_url}: {len(table_rows)}")

            for row in table_rows:
                a_tag = row.find("a", href=True)
                if a_tag:
                    row_href = a_tag["href"]
                    season = re.search(rf"/{seasons_pattern}/", row_href)
                    if season:
                        print(f"Match found for season: {season.group(0)}")

                        modified_href = re.sub(
                            r"(/[^/]+)$", r"/stats/teams\1", row_href
                        )
                        full_url = f"https://fbref.com{modified_href}"
                        season_stats_urls.append(full_url)

                        print(f"Final URL: {full_url}")

            time.sleep(3)  # Dynamic adjustment could be added here

    print(f"Total season stats URLs: {len(season_stats_urls)}")
    print(f"All season stats URLs:\n{season_stats_urls}")

    return season_stats_urls


def extract_data_from_url(url):
    try:
        # Fetch and parse the page content
        data = requests.get(url).text.replace("<!--", "").replace("-->", "")
        soup = BeautifulSoup(data, "html.parser")

        # Extract season and competition information
        season = re.search(r"/(\d{4}-\d{4})/", url).group(1)
        h2_element = soup.find("h2")
        competition = (
            " ".join(h2_element.find("span").get_text().split()[1:])
            if h2_element and h2_element.find("span")
            else pd.NA
        )

        # Initialize empty DataFrames
        df_for = pd.DataFrame()
        df_against = pd.DataFrame()

        # Extract the 'for' data table
        table_for = soup.find("table", {"id": "stats_squads_standard_for"})
        if table_for is not None:
            df_for = pd.read_html(StringIO(str(table_for)))[0]
            df_for.columns = [
                f"{i} {j}" if "Unnamed" not in i else j for i, j in df_for.columns
            ]
            df_for["Season"] = season
            df_for["Competition"] = competition

        # Extract the 'against' data table
        table_against = soup.find("table", {"id": "stats_squads_standard_against"})
        if table_against is not None:
            df_against = pd.read_html(StringIO(str(table_against)))[0]
            df_against.columns = [
                f"{i} {j}" if "Unnamed" not in i else j for i, j in df_against.columns
            ]
            df_against["Season"] = season
            df_against["Competition"] = competition

        # Rename relevant columns
        rename_for = {
            "Playing Time 90s": "90s",
            "Per 90 Minutes npxG": "npxG",
        }
        df_for = df_for.rename(rename_for, axis=1)

        rename_against = {
            "Playing Time 90s": "90s",
            "Per 90 Minutes npxG": "npxGC",
        }
        df_against = df_against.rename(rename_against, axis=1)

        # Keep only Squad, Season, Competition, and renamed columns
        selected_columns_for = ["Squad", "Season", "Competition"] + list(
            rename_for.values()
        )
        selected_columns_against = ["Squad", "Season", "Competition"] + list(
            rename_against.values()
        )

        if "Squad" in df_for.columns:
            df_for = df_for[selected_columns_for]
        if "Squad" in df_against.columns:
            df_against = df_against[selected_columns_against]

        df_against["Squad"] = df_against["Squad"].str.replace("vs ", "", regex=False)

        return df_for, df_against

    except Exception as e:
        print(f"An error occurred for URL: {url} - {e}")
        return pd.DataFrame(), pd.DataFrame()


def process_dataframes(df, is_for=True):
    def apply_league_multiplier(row):
        if row["Competition"] == "Premier League":
            return 1  # No change for Premier League
        elif row["Competition"] == "Championship":
            return 0.5 if is_for else 2  # Different multipliers for npxG and npxGC
        return 1  # Default multiplier if league is neither

    def weighted_avg(series, weights):
        return (series * weights).sum() / weights.sum()

    def process_team(group):
        num_seasons = len(group)
        group = group.sort_values(by="Season", ascending=False).reset_index(drop=True)

        # Define weights based on number of seasons
        if num_seasons == 1:
            recency_weights = pd.Series(
                [1], index=group.index
            )  # Single season gets weight of 1
        elif num_seasons == 2:
            recency_weights = pd.Series(
                [0.7, 0.3], index=group.index
            )  # Two seasons with weights 0.7 and 0.3
        else:
            recency_weights = pd.Series(
                [0.7, 0.2, 0.1], index=group.index
            )  # Three seasons with weights 0.7, 0.2, and 0.1

        # Ensure weights match the length of the group
        recency_weights = recency_weights.head(num_seasons)

        # Apply league multipliers
        if is_for:
            group["npxG"] *= group.apply(apply_league_multiplier, axis=1)
            series_to_weight = group["npxG"]
        else:
            group["npxGC"] *= group.apply(apply_league_multiplier, axis=1)
            series_to_weight = group["npxGC"]

        # Calculate weighted averages
        weighted_value = weighted_avg(series_to_weight, recency_weights)

        # Calculate the sum of the '90s' column
        total_90s = group["90s"].sum()

        return pd.Series(
            {
                "Squad": group["Squad"].iloc[0],
                "90s": total_90s,
                "npxG" if is_for else "npxGC": weighted_value,
            }
        )

    df_grouped = df.groupby("Squad")

    df_grouped = df_grouped[
        (
            ["Squad", "Season", "Competition", "90s", "npxG"]
            if is_for
            else ["Squad", "Season", "Competition", "90s", "npxGC"]
        )
    ]

    # Process each squad while excluding the grouping columns
    weighted_df = df_grouped.apply(process_team).reset_index(drop=True)

    return weighted_df


def main():
    desired_seasons = ["2023-2024", "2022-2023", "2021-2022"]
    season_stats_urls = generate_season_stats_urls(desired_seasons)

    combined_df_for = pd.DataFrame()
    combined_df_against = pd.DataFrame()

    for url in season_stats_urls:
        print(f"Processing URL: {url}")
        df_for, df_against = extract_data_from_url(url)

        if not df_for.empty and not df_against.empty:
            combined_df_for = pd.concat([combined_df_for, df_for], ignore_index=True)
            combined_df_against = pd.concat(
                [combined_df_against, df_against], ignore_index=True
            )
        else:
            print(f"No data extracted for URL: {url}")

    weighted_df_for = process_dataframes(combined_df_for, is_for=True)
    weighted_df_against = process_dataframes(combined_df_against, is_for=False)

    csv_file_path = "C:/Users/erknud3/fpl-optimization/model/data/Historic_Data"

    if not weighted_df_for.empty:
        weighted_df_for.to_csv(f"{csv_file_path}/team_stats_for.csv", index=False)
        print(f"'For' data successfully saved to team_stats_for.csv")
    else:
        print("No 'for' data to save.")

    if not weighted_df_against.empty:
        weighted_df_against.to_csv(
            f"{csv_file_path}/team_stats_against.csv", index=False
        )
        print(f"'Against' data successfully saved to team_stats_against.csv")
    else:
        print("No 'against' data to save.")

    # Debug: Check the data after processing
    print("Final 'For' data (sorted):")
    print(weighted_df_for.sort_values(by="npxG", ascending=False).head(10))
    print("Final 'Against' data (sorted):")
    print(weighted_df_against.sort_values(by="npxGC", ascending=True).head(10))


if __name__ == "__main__":
    main()
