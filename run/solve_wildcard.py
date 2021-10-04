import os
import sys
import pathlib
import json
import datetime

if __name__=="__main__":
    base_folder = pathlib.Path()
    sys.path.append(str(base_folder / "../src"))
    from multi_period_dev import connect, get_my_data, prep_data, solve_multi_period_fpl

    with open('wildcard_settings.json') as f:
        options = json.load(f)

    session, team_id = connect()
    my_data = get_my_data(session, team_id)
    data = prep_data(my_data, options)

    result = solve_multi_period_fpl(data, options)
    print(result['summary'])
    time_now = datetime.datetime.now()
    stamp = time_now.strftime("%Y-%m-%d_%H-%M-%S")
    result['picks'].to_csv(f"results/wildcard_{stamp}.csv")
    