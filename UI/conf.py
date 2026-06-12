from pathlib import Path
import sys

import yaml

from application.configuration import load_runtime_config_overrides


def _resource_path(*parts):
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent.joinpath(*parts))
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS).joinpath(*parts))
    candidates.append(Path.cwd().joinpath(*parts))
    candidates.append(Path(__file__).resolve().parents[1].joinpath(*parts))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


with open(_resource_path("conf.yaml"), 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)["Test_4_10"]

config.update(load_runtime_config_overrides())
