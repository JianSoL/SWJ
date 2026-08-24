import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from product import PRODUCT_INFO


DEFAULT_CONFIG_PROFILE = "Test_4_10"


@dataclass(frozen=True)
class RuntimePaths:
    package_dir: Path
    project_dir: Path
    resource_root: Path
    output_root: Path
    config_path: Path
    dbc_path: Path
    legacy_catalog_path: Path
    index_catalog_path: Path
    log_dir: Path
    theme_path: Path
    icon_path: Path
    alarm_path: Path
    profile: str
    frozen: bool


def is_frozen_app():
    return bool(getattr(sys, "frozen", False))


def _bundle_root():
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return None


def _first_existing(label, candidates):
    normalized = [Path(candidate).resolve() for candidate in candidates]
    for path in normalized:
        if path.exists():
            return path
    joined = ", ".join(str(path) for path in normalized)
    raise FileNotFoundError(f"{label} not found. Checked: {joined}")


def _resolve_runtime_config_path(frozen, output_root, candidates):
    if not frozen:
        return _first_existing("Runtime config", candidates)

    external_config_path = output_root / "conf.yaml"
    if external_config_path.exists():
        return external_config_path

    bundled_config_path = _first_existing("Runtime config", candidates)
    try:
        external_config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled_config_path, external_config_path)
        return external_config_path
    except OSError:
        return bundled_config_path


def build_runtime_paths(profile=None):
    package_dir = Path(__file__).resolve().parents[1]
    project_dir = package_dir.parent
    bundle_root = _bundle_root()
    frozen = is_frozen_app()

    resource_root = bundle_root or package_dir
    output_root = Path(sys.executable).resolve().parent if frozen else package_dir

    selected_profile = (
        profile
        or os.environ.get(PRODUCT_INFO.config_profile_env)
        or DEFAULT_CONFIG_PROFILE
    )
    log_dir = Path(
        os.environ.get(PRODUCT_INFO.log_dir_env, output_root / "log")
    ).expanduser()
    config_candidates = [
        resource_root / "conf.yaml",
        package_dir / "conf.yaml",
        project_dir / "conf.yaml",
    ]
    dbc_candidates = [
        resource_root / "DCFDV1.3.dbc",
        project_dir / "DCFDV1.3.dbc",
        package_dir / "DCFDV1.3.dbc",
    ]
    legacy_catalog_candidates = [
        resource_root / "SINGLE" / "BCU.yaml",
        package_dir / "SINGLE" / "BCU.yaml",
    ]
    index_catalog_candidates = [
        resource_root / "resources" / "index_catalog.json",
        package_dir / "resources" / "index_catalog.json",
    ]
    theme_candidates = [
        resource_root / "UI" / "release_theme.qss",
        package_dir / "UI" / "release_theme.qss",
    ]
    icon_candidates = [
        resource_root / "1.ico",
        package_dir / "1.ico",
    ]
    alarm_candidates = [
        resource_root / "alarm.wav",
        package_dir / "alarm.wav",
    ]

    return RuntimePaths(
        package_dir=package_dir,
        project_dir=project_dir,
        resource_root=resource_root,
        output_root=output_root,
        config_path=_resolve_runtime_config_path(
            frozen,
            output_root,
            config_candidates,
        ),
        dbc_path=_first_existing("DBC file", dbc_candidates),
        legacy_catalog_path=_first_existing(
            "Legacy signal catalog", legacy_catalog_candidates
        ),
        index_catalog_path=_first_existing(
            "Index catalog", index_catalog_candidates
        ),
        log_dir=log_dir,
        theme_path=_first_existing("Release theme", theme_candidates),
        icon_path=_first_existing("Window icon", icon_candidates),
        alarm_path=_first_existing("Alarm sound", alarm_candidates),
        profile=str(selected_profile),
        frozen=frozen,
    )


def required_release_files(runtime_paths):
    return {
        "config": runtime_paths.config_path,
        "dbc": runtime_paths.dbc_path,
        "legacy_catalog": runtime_paths.legacy_catalog_path,
        "index_catalog": runtime_paths.index_catalog_path,
        "theme": runtime_paths.theme_path,
        "icon": runtime_paths.icon_path,
        "alarm": runtime_paths.alarm_path,
        "driver": runtime_paths.project_dir / "ControlCANFD.dll",
    }
