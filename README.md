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

### Wilcard optimization

- Download and install Python and Git to your machine
- Donwload CBC optimization solver binary and add it to your environment path (example: https://youtu.be/DFXCXoR6Dvw?t=1642)
- Clone the repository
  
  `git clone git@github.com:sertalpbilal/FPL-Optimization-Tools.git fpl-optimization`

- Install required packages
  
  ``` shell
  cd fpl-optimization
  python -m pip install -r requirements.txt
  ```

- Navigate to `data` directory and copy login file without `sample` extension
  
  ``` shell
  cd data
  cp login.json.sample login.json
  ```

- Edit values inside `login.json` file:
  
  ``` json
  {
    "email": "myemail@email.com",
    "password": "mypassword"
  }
  ```

- Navigate to `run` directory
  
  `cd ..\run`

- Edit content of `wildcard_settings.json` file
  
  ``` json
    { 
        "horizon": 4,
        "use_wc": 8,
        "no_future_transfer": true,
        "randomized": false,
        "wc_limit": 1,
        "banned": [],
        "delete_tmp": true
    }
  ```

  - `horizon`: length of planning horizon
  - `use_wc`: GW number you want to use your wildcard
  - `no_future_transfer`: `true` or `false` whether you want to plan future transfers or not
  - `randomized`: `true` or `false` whether you would like to add random noise to EV
  - `banned`: list of banned player IDs

- Run the wildcard optimization
  
  ``` shell
  python solve_wildcard.py
  ```

- Find the optimal plans under `run\results` directory with timestamp
  
  ```
    > cd results
    > ls
    wildcard_2021-10-04_10-49-07.csv  wildcard_2021-10-04_10-54-50.csv
  ```

# License

[Apache-2.0 License](LICENSE)
