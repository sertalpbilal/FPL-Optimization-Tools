import pandas as pd
import requests
from io import StringIO
from bs4 import BeautifulSoup


def get_team_stats_new_season(url):
    try:
        # Fetch and parse the page content
        data = requests.get(url).text.replace("<!--", "").replace("-->", "")
        soup = BeautifulSoup(data, "html.parser")

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

        # Extract the 'against' data table
        table_against = soup.find("table", {"id": "stats_squads_standard_against"})
        if table_against is not None:
            df_against = pd.read_html(StringIO(str(table_against)))[0]
            df_against.columns = [
                f"{i} {j}" if "Unnamed" not in i else j for i, j in df_against.columns
            ]

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
        selected_columns_for = ["Squad"] + list(rename_for.values())
        selected_columns_against = ["Squad"] + list(rename_against.values())

        if "Squad" in df_for.columns:
            df_for = df_for[selected_columns_for]
        if "Squad" in df_against.columns:
            df_against = df_against[selected_columns_against]

        # Remove the 'vs ' prefix from the 'Squad' column in combined_df_against
        df_against["Squad"] = df_against["Squad"].str.replace("vs ", "", regex=False)

        return df_for, df_against

    except Exception as e:
        print(f"An error occurred for URL: {url} - {e}")
        return pd.DataFrame(), pd.DataFrame()


def calculate_weighted_stats(df, is_for=True, weight_new_data=1.0):
    """Calculate weighted stats with additional weight for new data."""
    # Calculate total 90s for normalization
    total_90s = df["90s"] + df["90s_new"]

    # Apply additional weight to new data
    weight_old_data = 1.0
    weight_new_data = float(weight_new_data)

    if is_for:
        df["weighted_npxG"] = (
            (df["npxG"] * df["90s"] / total_90s * weight_old_data)
            + (df["npxG_new"] * df["90s_new"] / total_90s * weight_new_data)
        ).round(2)
    else:
        df["weighted_npxGC"] = (
            (df["npxGC"] * df["90s"] / total_90s * weight_old_data)
            + (df["npxGC_new"] * df["90s_new"] / total_90s * weight_new_data)
        ).round(2)

    return df


def main():
    weight_new_data = 1.5

    url = "https://fbref.com/en/comps/9/stats/Premier-League-Stats"
    teams_previous_seasons_for = pd.read_csv(
        "C:/Users/erknud3/fpl-optimization/model/data/Historic_Data/team_stats_for.csv"
    )
    teams_previous_seasons_against = pd.read_csv(
        "C:/Users/erknud3/fpl-optimization/model/data/Historic_Data/team_stats_against.csv"
    )

    df_for, df_against = get_team_stats_new_season(url)

    new_df_for = pd.DataFrame()
    new_df_against = pd.DataFrame()

    df_for, df_against = get_team_stats_new_season(
        "https://fbref.com/en/comps/9/stats/Premier-League-Stats"
    )

    if not df_for.empty and not df_against.empty:
        new_df_for = pd.concat([new_df_for, df_for], ignore_index=True)
        new_df_against = pd.concat([new_df_against, df_against], ignore_index=True)
    else:
        print(f"No data extracted for URL: {url}")

    new_season_for = pd.merge(
        teams_previous_seasons_for,
        new_df_for,
        on="Squad",
        how="inner",
        suffixes=("", "_new"),
    )
    new_season_against = pd.merge(
        teams_previous_seasons_against,
        new_df_against,
        on="Squad",
        how="inner",
        suffixes=("", "_new"),
    )

    new_season_for.insert(0, "team_id", range(1, 21))
    new_season_against.insert(0, "team_id", range(1, 21))

    # Calculate weighted stats
    new_season_for = calculate_weighted_stats(
        new_season_for, is_for=True, weight_new_data=weight_new_data
    )
    new_season_against = calculate_weighted_stats(
        new_season_against, is_for=False, weight_new_data=weight_new_data
    )

    # max_mp = new_season_for["90s_new"].max().astype(int)

    csv_file_path = "C:/Users/erknud3/fpl-optimization/model/data/New_Season_Data"

    if not new_season_for.empty:
        new_season_for.to_csv(f"{csv_file_path}/teams_new_season_for.csv", index=False)
        print(f"'For' data successfully saved to teams_new_season_for.csv")
    else:
        print("No 'for' data to save.")

    if not new_season_against.empty:
        new_season_against.to_csv(
            f"{csv_file_path}/teams_new_season_against.csv", index=False
        )
        print(f"'Against' data successfully saved to teams_new_season_against.csv")
    else:
        print("No 'against' data to save.")


if __name__ == "__main__":
    main()
