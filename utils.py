import json
import random
import string
from itertools import product

from paths import DATA_DIR


def load_settings():
    with open(DATA_DIR / "comprehensive_settings.json") as f:
        options = json.load(f)
    with open(DATA_DIR / "user_settings.json") as f:
        options = {**options, **json.load(f)}

    return options


def get_random_id(n):
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def xmin_to_prob(xmin, sub_on=0.5, sub_off=0.3):
    start = min(max((xmin - 25 * sub_on) / (90 * (1 - sub_off) + 65 * sub_off - 25 * sub_on), 0.001), 0.999)
    return start + (1 - start) * sub_on


def get_dict_combinations(my_dict):
    keys = my_dict.keys()
    for key in keys:
        if my_dict[key] is None or len(my_dict[key]) == 0:
            my_dict[key] = [None]
    all_combs = [dict(zip(my_dict.keys(), values, strict=False)) for values in product(*my_dict.values())]
    feasible_combs = []
    for comb in all_combs:
        c_values = [i for i in comb.values() if i is not None]
        if len(c_values) == len(set(c_values)):
            feasible_combs.append({k: [v] for k, v in comb.items() if v is not None})
        # else we have a duplicate
    return feasible_combs


def load_config_files(config_paths):
    """
    Load and merge multiple configuration files.
    Files are merged in order, with later files overriding earlier ones.
    """
    merged_config = {}
    if not config_paths:
        return merged_config

    paths = config_paths.split(";")
    for path in paths:
        stripped_path = path.strip()
        if not path:
            continue
        try:
            with open(stripped_path) as f:
                config = json.load(f)
                merged_config.update(config)
        except FileNotFoundError:
            print(f"Warning: Configuration file {stripped_path} not found")
        except json.JSONDecodeError:
            print(f"Warning: Configuration file {stripped_path} is not valid JSON")

    return merged_config
