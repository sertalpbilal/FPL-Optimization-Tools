import os
import shutil
from pathlib import Path
from datetime import datetime
import pytz

downloads_folder = Path.home() / "Downloads"
data_folder = Path(
    "C:/Users/erknud3/OneDrive - Norgesgruppen/Skrivebord/fpl-optimization/data"
)
filename_prefix = "fplreview"

# Oslo time zone
oslo_tz = pytz.timezone("Europe/Oslo")

# Check downloads folder for fplreview.csv
downloaded_files = [file for file in downloads_folder.glob(f"{filename_prefix}*.csv")]
data_files = [file for file in data_folder.glob(f"{filename_prefix}*.csv")]

if not downloaded_files and not data_files:
    print("No fplreview.csv files found.")
else:
    try:
        # Check which downloaded file has the latest modification date
        latest_downloaded_file = max(
            downloaded_files, key=os.path.getmtime, default=None
        )
        latest_data_file = max(data_files, key=os.path.getmtime, default=None)

        if latest_data_file and (
            not latest_downloaded_file
            or os.path.getmtime(latest_data_file)
            > os.path.getmtime(latest_downloaded_file)
        ):
            latest_data_date = (
                datetime.utcfromtimestamp(os.path.getmtime(latest_data_file))
                .replace(tzinfo=pytz.utc)
                .astimezone(oslo_tz)
                .strftime("%d-%m-%Y %H:%M:%S")
            )
            print(
                f"Keeping fplreview.csv in data directory (Date modified: {latest_data_date})"
            )
        else:
            # Move and rename the latest downloaded file to the data directory
            if latest_downloaded_file:
                date_modified_before_rename = (
                    datetime.utcfromtimestamp(os.path.getmtime(latest_downloaded_file))
                    .replace(tzinfo=pytz.utc)
                    .astimezone(oslo_tz)
                    .strftime("%d-%m-%Y %H:%M:%S")
                )

                new_filename = f"{filename_prefix}_12gws.csv"
                new_path = data_folder / new_filename

                if new_path.is_file():
                    os.remove(new_path)

                shutil.move(latest_downloaded_file, new_path)

                print(
                    f"{new_filename} file successfully moved from downloads to data directory (Date modified before rename: {date_modified_before_rename})"
                )
            else:
                print("No fplreview.csv file in downloads folder")

    except Exception as e:
        print(f"An error occurred: {e}")
