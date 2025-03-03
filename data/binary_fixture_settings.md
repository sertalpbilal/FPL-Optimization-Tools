## Binary Files Generator Fixture Configuration

This file contains the binary file generator fixture configurations to be used by simulations.py for generating binary files. Note that this will only be used if "generate_binary_files" is set to true in regular_settings.json, otherwise simulations.py will assume the binary files already exist.


### Instructions

1. Set the fixtures in fplreview so there are no BGW/DGW, i.e. each team should have the fixtures as originally scheduled in their respective GW. Download that csv, name it fplreview_original.csv, and place it in the '../data' directory

2. Configure the DGW/BGW fixture settings for each binary file in the JSON section below (example provided). For each team, the key represents the target GW to move EV to (usually to become a DGW) while the value represenst the original GW to move the EV from (usually to become a BGW). For example in the sample configuration provided below, in fplreview_binary_1 EV will be moved from GW34 to GW33 for Bournemount, Man Utd, Man City, and Aston Villa - and from GW34 to GW36 for Newcastle and Ipswich.

3. To generate the binary files simply make sure "generate_binary_files" is set to true in regular_settings.json, set the corresponding binary weights, and run simulations.py with use_binaries=y.

### JSON Fixture Configuration

```json
{
    "fplreview_binary_1.csv": {
        "Bournemouth": { "33": "34" },
        "Man Utd": { "33": "34" },
        "Man City": { "33": "34" },
        "Aston Villa": { "33": "34" },
        "Newcastle": { "36": "34" },
        "Ipswich": { "36": "34" }
    },
    "fplreview_binary_2.csv": {
        "Bournemouth": { "33": "34", "36": "37" },
        "Man Utd": { "33": "34" },
        "Man City": { "33": "34", "36": "37" },
        "Aston Villa": { "33": "34" },
        "Newcastle": { "36": "34" },
        "Ipswich": { "36": "34" }
    },
    "fplreview_binary_3.csv": {
        "Man City": { "33": "34" },
        "Aston Villa": { "33": "34" },
        "Newcastle": { "36": "34" },
        "Ipswich": { "36": "34" },
        "Arsenal": { "36": "34" },
        "Crystal Palace": { "36": "34" }
    }      
}
```
