import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from domain.legacy_catalog import LegacySignalCatalog


def _definition_by_name(catalog, name):
    matches = [definition for definition in catalog.definitions if definition.name == name]
    if len(matches) != 1:
        raise AssertionError(f"expected one definition for {name!r}, got {len(matches)}")
    return matches[0]


class LegacyCatalogTests(unittest.TestCase):
    def test_yaml_catalog_contains_all_migrated_signals(self):
        catalog = LegacySignalCatalog.from_yaml(PROJECT_DIR / "SINGLE" / "BCU.yaml")

        self.assertEqual(len(catalog.definitions), 101)
        self.assertEqual(len(catalog.logged_signal_names), 101)

    def test_yaml_catalog_rejects_missing_required_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path = Path(temp_dir) / "BCU.yaml"
            catalog_path.write_text(
                "schema_version: 1\nsignals:\n  - id: '0xE'\n    name: SOC\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "missing"):
                LegacySignalCatalog.from_yaml(catalog_path)

    def test_60s_power_and_current_match_bcu615_indices_and_units(self):
        catalog = LegacySignalCatalog.from_yaml(PROJECT_DIR / "SINGLE" / "BCU.yaml")

        expected = (
            ("60S\u6700\u5927\u5141\u8bb8\u653e\u7535\u7535\u6d41[0.1A]", 0x1AD, "0.1A"),
            ("60S\u6700\u5927\u5141\u8bb8\u653e\u7535\u529f\u7387[10W]", 0x1AE, "10W"),
            ("60S\u6700\u5927\u5141\u8bb8\u5145\u7535\u7535\u6d41[0.1A]", 0x1AF, "0.1A"),
            ("60S\u6700\u5927\u5141\u8bb8\u5145\u7535\u529f\u7387[10W]", 0x1B0, "10W"),
        )

        for name, signal_id, unit in expected:
            definition = _definition_by_name(catalog, name)
            self.assertEqual(definition.signal_id, signal_id)
            self.assertEqual(definition.unit, unit)

    def test_precharge_parameters_are_shown_in_request_group_2(self):
        catalog = LegacySignalCatalog.from_yaml(PROJECT_DIR / "SINGLE" / "BCU.yaml")

        expected_rows = [
            ("最大允许预充时间[0.1S]", 0x90479, "0.1S", 9),
            ("预充电压完成百分比/压差[%/0.1V]", 0x9047A, "%/0.1V", 10),
            ("并机均充开启与结束电压百分比/压差[%/0.1V]", 0x9047B, "%/0.1V", 11),
            ("最小预充时间[0.1S]", 0x9047C, "0.1S", 12),
            ("预充电流限制[0.1A]", 0x9047D, "0.1A", 13),
        ]

        for name, signal_id, unit, row_index in expected_rows:
            definition = _definition_by_name(catalog, name)
            self.assertEqual(definition.signal_id, signal_id)
            self.assertEqual(definition.unit, unit)
            self.assertEqual(definition.table_index, 1)
            self.assertEqual(definition.row_index, row_index)


if __name__ == "__main__":
    unittest.main()
