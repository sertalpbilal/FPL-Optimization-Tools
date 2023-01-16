# FPL Optimization Repository

This repository is a collection of optimization tutorials and recipes for Fantasy Premier League (FPL).

Python code mainly use `pandas` for data management and `sasoptpy` for optimization modeling.

It is being actively developed. The content and the structure of the repository might change.

## Tutorials

If you are interested in using optimization for FPL, see my YouTube tutorials on the subject.

### Python

Link: https://youtube.com/playlist?list=PLrIyJJU8_viOags1yudB_wyafRuTNs1Ed

Python tutorials include following topics

- Goalkeeper selection problem
- Single-period expected value maximization (squad, lineup, captain)
- Multi-period expected value maximization (squad, lineup, captain)
- Alternative solution generation
- Multi-objective optimization (2-Step and Weight methods)
- Bench decisions
- Auto-bench weights and iterative solution for nonlinear case
- Noise in expected values
- Sensitivity analysis
- Data collection from FPL API with login
- Wildcard (chip) optimization

## Excel

Link: https://youtube.com/playlist?list=PLrIyJJU8_viOLw3BovPDx5QLKkCb8XOTp

My Excel tutorials are rather short but might give you an idea what optimization is capable of doing.
Reach out to me if you need the raw data to give it a try.

- Goalkeeper selection problem
- Single-period expected value maximization (squad, lineup, captain)
- Multi-period expected value maximization (squad, lineup, captain)

## Instructions

### Installation Steps

You will need to follow steps below to install required platform and also optimization solver (CBC).


- Download and install Python and Git to your machine
- Download CBC optimization solver binary and add it to your environment path (example: https://youtu.be/DFXCXoR6Dvw?t=1642)
- Clone the repository

  `git clone https://github.com/sertalpbilal/FPL-Optimization-Tools.git fpl-optimization`

- Install required packages

  ``` shell
  cd fpl-optimization
  python -m pip install -r requirements.txt
  ```

- Download FPLReview projections and save it under `data` and rename it to `fplreview.csv`

- Navigate to `run` directory

  `cd ..\run`

  And run either `solve_regular.py` (for regular GW solve) or `solve_wildcard.py` (for wildcard optimization)
  See instructions below.

- Log in FPL from your browser and open
  https://fantasy.premierleague.com/api/my-team/MY_TEAM_ID/
  after replacing `MY_TEAM_ID` with your team id.
  Copy the content of the page into `data\team.json` file, by creating one.

  A sample team.json file is provided for your reference: `team.json.sample`

### Multi-period GW optimization


- Edit content of `regular_settings.json` file

  ``` json
    {
        "horizon": 5,
        "ft_value": 1.5,
        "itb_value": 0.2,
        "decay_base": 0.84,
        "no_future_transfer": true,
        "no_transfer_last_gws": 0,
        "randomized": false,
        "xmin_lb": 2,
        "bench_weights": {"0": 0.03, "1": 0.21, "2": 0.06, "3": 0.003},
        "banned": [],
        "locked": [],
        "delete_tmp": true,
        "secs": 300,
        "use_cmd": false,
        "future_transfer_limit": null,
        "no_transfer_gws": [],
        "booked_transfers": [],
        "use_wc": null,
        "use_bb": null,
        "use_fh": null,
        "chip_limits": {"bb": 0, "wc": 0, "fh": 0, "tc": 0},
        "num_transfers": null,
        "hit_limit": null,
        "preseason": false,
        "cbc_path": "",
        "no_opposing_play": false,
        "pick_prices": {"G": "", "D": "", "M": "", "F": ""},
        "iteration": 1,
        "iteration_criteria": "this_gw_transfer_in",
        "datasource" : "review",
        "data_weights": {"review": 50, "review-odds": 25, "mikkel": 15, "kiwi": 10},
        "export_data": "final.csv"
    }
  ```

  - `horizon`: length of planning horizon
  - `ft_value`: value assigned to the extra free transfer
  - `itb_value`: value assigned to having 1.0 extra budget
  - `decay_base`: value assigned to decay rate of expected points
  - `no_future_transfer`: `true` or `false` whether you want to plan future transfers or not
  - `no_transfer_last_gws`: the number of gws at the end of the period you want to ban transfers
  - `randomized`: `true` or `false` whether you would like to add random noise to EV
  - `xmin_lb`: cut-off for dropping players below this many minutes expectation
  - `bench_weights`: percentage weights in objective for bench players (gk and 3 outfield)
  - `banned`: list of banned player IDs
  - `locked`: list of player IDs to always have during the horizon (e.g. `233` for Salah)
  - `delete_tmp`: `true` or `false` whether to delete generated temporary files after solve
  - `secs`: time limit for the solve (in seconds)
  - `use_cmd`: whether to use `os.system` or `subprocess` for running solver, default is `false`
  - `future_transfer_limit`: upper bound how many transfers are allowed in future GWs
  - `no_transfer_gws`: list of GW numbers where transfers are not allowed
  - `booked_transfers`: list of booked transfers for future gameweeks, needs to have a `gw` key and at least one of `transfer_in` or `transfer_out` with the player ID. For example, to book a transfer of buying Kane (427) on GW5 and selling him on GW7, use

    `"booked_transfers": [{"gw": 5, "transfer_in": 427}, {"gw": 7, "transfer_out": 427}]`
  - `use_wc`: GW to use wildcard (fixed)
  - `use_bb`: GW to use bench boost (fixed)
  - `use_fh`: GW to use free hit (fixed)
  - `chip_limits`: how many chips of each kind can be used by solver (you need to set it to at least 1 when force using a chip)
  - `num_transfers`: fixed number of transfers for this GW
  - `hit_limit`: limit on total hits can be taken by the solver for entire horizon
  - `preseason`: solve flag for GW1 where team data is not important
  - `cbc_path`: binary location of the cbc solver (`bin` folder)
  - `no_opposing_play`: `true` if you do not want to have players in your lineup playing against each other in a GW
  - `pick_prices`: price points of players you want to force in a comma separated string
    For example, to force two 11.5M forwards, and one 8M midfielder, use
    `"pick_prices": {"G": "", "D": "", "M": "8", "F": "11.5,11.5"}`
  - `iteration`: number of different solutions to be generated, the criteria is controlled by `iteration_criteria`
  - `iteration_criteria`: rule on separating what a different solution mean, such as `this_gw_transfer_in` will force to replace player to buy current GW in each solution, while `this_gw_transfer_in_out` can find an alternative move with either bought or sold players to be different.
  - `datasource` : `review`, `kiwi`, `mikkel` or `avg` specifies the data to be used.

    - `review` requires `fplreview.csv` file
    - `review-odds` requires `fplreview-odds.csv` file
    - `kiwi` requires `kiwi.csv` file
    - `mikkel` requires `TransferAlgorithm.csv`, file
    - `mixed` requires an additional parameter `data_weights`, and any corresponding files mentioned above
  
    under `data` folder to be present
  - `data_weights`: weight percentage for each data source, given as a dictionary, where keys should be one of valid data sources
  - `export_data`: option for exporting final data as a CSV file (when using `mixed` data)

- Run the multi-period optimization

  ``` shell
  python solve_regular.py
  ```

- Find the optimal plans under `data\results` directory with timestamp

  ```
    > cd ../data/results
    > ls
    regular_2021-11-04_10-00-00.csv
  ```

## Run in Docker

A Dockerised version of the solver is included in this repo which
includes all dependencies required to run the program and save
results.  Docker must be installed on the host machine.

In order to run the solver via Docker, you'll firstly need to follow the instructions in the `Installation Steps` section to add the following files to the `/data` folder:

 - `team.json`
 - `regular_settings.json`
 - `fplreview.csv`

Then, to pull the Docker image, build it, and then run the solver, simply run the following command:

```shell
> docker-compose up
```

After the initial setup, re-running this command will skip the pull and build steps and simply run the solver.

# License

[Apache-2.0 License](LICENSE)
