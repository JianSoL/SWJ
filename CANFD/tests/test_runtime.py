import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.config_loader import (
    load_runtime_config,
    resolve_active_cluster_addresses,
    save_runtime_config_fields,
)
from application.runtime import build_runtime_paths, required_release_files


class RuntimePathTests(unittest.TestCase):
    def test_runtime_paths_resolve_source_tree_release_files(self):
        paths = build_runtime_paths(profile="Test_4_10")

        self.assertEqual(paths.profile, "Test_4_10")
        self.assertTrue(paths.config_path.exists())
        self.assertTrue(paths.dbc_path.exists())
        self.assertTrue(paths.legacy_catalog_path.exists())
        self.assertEqual(paths.legacy_catalog_path.name, "BCU.yaml")
        self.assertTrue(paths.index_catalog_path.exists())
        self.assertTrue(paths.theme_path.exists())
        self.assertTrue(paths.icon_path.exists())
        self.assertTrue(paths.alarm_path.exists())

        missing = [
            label
            for label, path in required_release_files(paths).items()
            if not Path(path).exists()
        ]
        self.assertEqual(missing, [])

    def test_runtime_paths_honor_profile_and_log_dir_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "DCBMS_PROFILE": "Test_4_10",
                    "DCBMS_LOG_DIR": temp_dir,
                },
            ):
                paths = build_runtime_paths()

        self.assertEqual(paths.profile, "Test_4_10")
        self.assertEqual(paths.log_dir, Path(temp_dir))


class ConfigLoaderTests(unittest.TestCase):
    def test_load_runtime_config_adds_profile_marker(self):
        config = load_runtime_config(PROJECT_DIR / "conf.yaml", profile="Test_4_10")

        self.assertEqual(config["_CONFIG_PROFILE"], "Test_4_10")
        self.assertIn("BCU_NUM", config)
        self.assertIn("ADDRESLIST", config)

    def test_load_runtime_config_rejects_unknown_profile(self):
        with self.assertRaises(KeyError):
            load_runtime_config(PROJECT_DIR / "conf.yaml", profile="missing")

    def test_load_runtime_config_accepts_exact_cluster_address_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "conf.yaml"
            config_path.write_text(
                (
                    "Release:\n"
                    "  BCU_NUM: 2\n"
                    "  DEVICE_INDEX: 0\n"
                    "  CHANNEL_INDEX: 0\n"
                    "  ADDRESLIST: ['A0', 'A1']\n"
                ),
                encoding="utf-8",
            )

            loaded = load_runtime_config(config_path, profile="Release")

        self.assertEqual(loaded["BCU_NUM"], 2)
        self.assertEqual(loaded["ADDRESLIST"], ["A0", "A1"])
        self.assertEqual(resolve_active_cluster_addresses(loaded), ["A0", "A1"])

    def test_optional_address_00_is_active_but_not_counted(self):
        runtime_config = {
            "BCU_NUM": 2,
            "ADDRESLIST": ["00", "A0", "A1", "A2"],
        }

        self.assertEqual(
            resolve_active_cluster_addresses(runtime_config),
            ["00", "A0", "A1"],
        )

    def test_save_runtime_config_fields_updates_selected_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "conf.yaml"
            config_path.write_text(
                (
                    "Release:\n"
                    "  BCU_NUM: 1\n"
                    "  DEVICE_INDEX: 0\n"
                    "  CHANNEL_INDEX: 0\n"
                    "  ADDRESLIST:\n"
                    "    - 'A0'\n"
                ),
                encoding="utf-8",
            )

            saved = save_runtime_config_fields(
                config_path,
                "Release",
                {
                    "BCU_NUM": 2,
                    "LECU_NUM": 4,
                    "ADDRESLIST": ["B0", "B1"],
                    "ADDRESLIST0x": ["0xB0", "0xB1"],
                },
            )
            loaded = load_runtime_config(config_path, profile="Release")

        self.assertEqual(saved["BCU_NUM"], 2)
        self.assertEqual(saved["_CONFIG_PROFILE"], "Release")
        self.assertEqual(loaded["BCU_NUM"], 2)
        self.assertEqual(loaded["LECU_NUM"], 4)
        self.assertEqual(loaded["ADDRESLIST"], ["B0", "B1"])


if __name__ == "__main__":
    unittest.main()
