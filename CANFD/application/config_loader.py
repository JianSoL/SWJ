from pathlib import Path

import yaml


def load_runtime_config(config_path, profile="Test_4_10"):
    with open(Path(config_path), "r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)[profile]
