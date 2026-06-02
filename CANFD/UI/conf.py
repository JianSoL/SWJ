from pathlib import Path

import yaml


CONFIG_PATH = Path(__file__).resolve().parents[1] / "conf.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)["Test_4_10"]
