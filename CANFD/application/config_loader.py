from pathlib import Path

import yaml

from application.runtime import DEFAULT_CONFIG_PROFILE


REQUIRED_CONFIG_KEYS = (
    "BCU_NUM",
    "ADDRESLIST",
    "DEVICE_INDEX",
    "CHANNEL_INDEX",
)
UNASSIGNED_CLUSTER_ADDRESS = "00"


def resolve_active_cluster_addresses(runtime_config):
    """Return optional address 00 plus the configured numbered clusters.

    ``BCU_NUM`` counts only numbered clusters. Address ``00`` is an optional
    protocol target for an unassigned BCU and is active only when explicitly
    present in ``ADDRESLIST``.
    """
    bcu_num = int(runtime_config["BCU_NUM"])
    if bcu_num < 0:
        raise ValueError("BCU_NUM cannot be negative")

    addresses = [
        str(address).strip().upper()
        for address in runtime_config["ADDRESLIST"]
    ]
    if len(addresses) != len(set(addresses)):
        raise ValueError("ADDRESLIST contains duplicate addresses")

    numbered_addresses = [
        address
        for address in addresses
        if address != UNASSIGNED_CLUSTER_ADDRESS
    ]
    if len(numbered_addresses) < bcu_num:
        raise ValueError(
            f"BCU_NUM={bcu_num} needs at least {bcu_num} numbered addresses, "
            f"got {len(numbered_addresses)}"
        )

    active_addresses = []
    if UNASSIGNED_CLUSTER_ADDRESS in addresses:
        active_addresses.append(UNASSIGNED_CLUSTER_ADDRESS)
    active_addresses.extend(numbered_addresses[:bcu_num])
    return active_addresses


def _validate_runtime_config(runtime_config, profile, config_path):
    missing_keys = [
        key
        for key in REQUIRED_CONFIG_KEYS
        if key not in runtime_config
    ]
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise KeyError(
            f"Config profile {profile!r} in {config_path} is missing: {joined}"
        )

    try:
        resolve_active_cluster_addresses(runtime_config)
    except ValueError as exc:
        raise ValueError(
            f"Config profile {profile!r} in {config_path}: {exc}"
        ) from exc


def load_runtime_config(config_path, profile=DEFAULT_CONFIG_PROFILE):
    config_path = Path(config_path)
    with open(config_path, "r", encoding="utf-8") as config_file:
        all_profiles = yaml.safe_load(config_file) or {}

    if profile not in all_profiles:
        available = ", ".join(sorted(str(key) for key in all_profiles))
        raise KeyError(
            f"Config profile {profile!r} not found in {config_path}. "
            f"Available profiles: {available}"
        )

    runtime_config = dict(all_profiles[profile])
    runtime_config["_CONFIG_PROFILE"] = profile
    _validate_runtime_config(runtime_config, profile, config_path)
    return runtime_config


def save_runtime_config_fields(config_path, profile, updates):
    config_path = Path(config_path)
    with open(config_path, "r", encoding="utf-8") as config_file:
        all_profiles = yaml.safe_load(config_file) or {}

    if profile not in all_profiles:
        available = ", ".join(sorted(str(key) for key in all_profiles))
        raise KeyError(
            f"Config profile {profile!r} not found in {config_path}. "
            f"Available profiles: {available}"
        )

    runtime_config = dict(all_profiles[profile] or {})
    runtime_config.update(dict(updates))
    _validate_runtime_config(runtime_config, profile, config_path)
    all_profiles[profile] = runtime_config

    with open(config_path, "w", encoding="utf-8") as config_file:
        yaml.safe_dump(
            all_profiles,
            config_file,
            allow_unicode=True,
            sort_keys=False,
        )

    saved_config = dict(runtime_config)
    saved_config["_CONFIG_PROFILE"] = profile
    return saved_config
