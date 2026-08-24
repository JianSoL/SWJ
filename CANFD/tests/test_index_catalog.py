import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from domain.index_catalog import IndexCatalog


class IndexCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = IndexCatalog.from_json(
            PROJECT_DIR / "resources" / "index_catalog.json"
        )
        cls.config = {
            "BCU_NUM": 2,
            "LECU_NUM": 4,
            "CELL_NUM": 104,
            "Alarm_name_key": {"001": "单体电压过高"},
        }

    def test_resolves_fixed_system_current_indexes(self):
        hall = self.catalog.resolve(0x315, self.config)
        shunt = self.catalog.resolve(0x316, self.config)

        self.assertEqual(hall.symbol, "VAR_HALL_CURR")
        self.assertIn("霍尔", hall.name)
        self.assertEqual(shunt.symbol, "VAR_SHUNT_CURR")
        self.assertIn("分流器", shunt.name)

    def test_resolves_60s_power_and_current_protocol_units(self):
        expected = (
            (0x1AD, "VAR_SYS_ALLOW_DSCH_60SCURR", "0.1A"),
            (0x1AE, "VAR_SYS_ALLOW_DSCH_60SPOWER", "10W"),
            (0x1AF, "VAR_SYS_ALLOW_CHRG_60SCURR", "0.1A"),
            (0x1B0, "VAR_SYS_ALLOW_CHRG_60SPOWER", "10W"),
        )

        for data_id, symbol, unit in expected:
            resolution = self.catalog.resolve(data_id, self.config)
            self.assertEqual(resolution.symbol, symbol)
            self.assertEqual(resolution.unit, unit)

    def test_resolves_lecu_modules_with_11_field_stride(self):
        module_one = self.catalog.resolve(0x101E, self.config)
        module_two = self.catalog.resolve(0x14D6, self.config)
        cell_voltage = self.catalog.resolve(0x1042, self.config)

        self.assertEqual(self.catalog.constants["VAR_LECU_CELL_MAX_NUM"], 11)
        self.assertEqual(self.catalog.constants["LECU_DATA_LENGTH"], 0x4B8)
        self.assertEqual(module_one.symbol, "VAR_LECU_UINT_BALAN_STATE_CFG00_15")
        self.assertEqual(module_two.symbol, "VAR_LECU_UINT_BALAN_STATE_CFG00_15")
        self.assertEqual(module_two.location, "模组2")
        self.assertEqual(cell_voltage.symbol, "VAR_LECU_CELL_VOLT")
        self.assertEqual(cell_voltage.location, "模组1/单体1")

    def test_resolves_system_and_alarm_parameters(self):
        precharge = self.catalog.resolve(0x90479, self.config)
        alarm_level = self.catalog.resolve(0x94900, self.config)

        self.assertEqual(precharge.symbol, "PAR_SYS_PRECHARGE_MODE")
        self.assertEqual(precharge.unit.upper(), "0.1S")
        self.assertEqual(alarm_level.symbol, "PAR_ALM_LEVEL1")
        self.assertIn("告警001", alarm_level.location)
        self.assertIn("单体电压过高", alarm_level.location)

    def test_catalog_contains_replaced_alarm_fields_47_to_49(self):
        expected = (
            (46, "ALARM_BCU_ID_47", "电池簇充电电池模块电压极差"),
            (47, "ALARM_BCU_ID_48", "电池簇放电电池模块电压极差"),
            (48, "ALARM_BCU_ID_49", "高压箱风扇故障"),
        )

        for offset, symbol, name in expected:
            entry = self.catalog.alarm_ids[offset]
            self.assertEqual(entry["offset"], offset)
            self.assertEqual(entry["symbol"], symbol)
            self.assertEqual(entry["name"], name)
            self.assertFalse(entry["reserved"])

    def test_keeps_business_fields_ending_in_num(self):
        lecu_count = self.catalog.resolve(590849, self.config)
        balance_temp_count = self.catalog.resolve(0x90462, self.config)
        cluster_balance_temp_count = self.catalog.resolve(633, self.config)
        lecu_balance_temp_count = self.catalog.resolve(
            self.catalog.constants["ID_PAR_LECU_START"] + 12,
            self.config,
        )

        self.assertTrue(lecu_count.known)
        self.assertEqual(lecu_count.data_id, 0x90401)
        self.assertEqual(lecu_count.symbol, "PAR_SYS_LECU_NUM")
        self.assertTrue(balance_temp_count.known)
        self.assertEqual(balance_temp_count.symbol, "PAR_SYS_LECU_T_BALANCE_NUM")
        self.assertTrue(cluster_balance_temp_count.known)
        self.assertEqual(
            cluster_balance_temp_count.symbol,
            "VAR_SYS_CONFIG_TEMP_BALANCE_NUM",
        )
        self.assertTrue(lecu_balance_temp_count.known)
        self.assertEqual(lecu_balance_temp_count.symbol, "PAR_LECU_TEMP_BALANCE_NUM")
        self.assertIn(
            590849,
            {entry.data_id for entry in self.catalog.iter_entries(self.config)},
        )

    def test_resolves_new_firmware_balance_temperature_indexes(self):
        box_temp_max = self.catalog.resolve(420, self.config)
        balance_temp = self.catalog.resolve(0x104A, self.config)

        self.assertEqual(box_temp_max.symbol, "VAR_SYS_BOX_TEMP_MAX")
        self.assertEqual(box_temp_max.unit, "0.1℃")
        self.assertEqual(balance_temp.symbol, "VAR_LECU_CELL_BALANCE_TEMP")
        self.assertEqual(balance_temp.unit, "0.1℃")
        self.assertEqual(balance_temp.location, "模组1/单体1")

    def test_resolves_energy_units_from_firmware(self):
        expected = (
            (0x1FD, "VAR_SYS_SINGLE_CHRG_KWH", "0.1KWH"),
            (0x1FE, "VAR_SYS_SINGLE_DISCHRG_KWH", "0.1KWH"),
            (0x252, "VAR_SYS_SOE_RADE", "0.01KWH"),
            (0x253, "VAR_SYS_SOE_ACE", "0.01KWH"),
            (0x90885, "PAR_RUN_TOTAL_CHRG_KWH_LOW", "0.01KWH"),
            (0x90886, "PAR_RUN_TOTAL_CHRG_KWH_HIGH", "0.01KWH"),
            (0x90887, "PAR_RUN_TOTAL_DSCH_KWH_LOW", "0.01KWH"),
            (0x90888, "PAR_RUN_TOTAL_DSCH_KWH_HIGH", "0.01KWH"),
        )

        for data_id, symbol, unit in expected:
            resolution = self.catalog.resolve(data_id, self.config)
            self.assertTrue(resolution.known)
            self.assertEqual(resolution.symbol, symbol)
            self.assertEqual(resolution.unit.upper(), unit)

    def test_browser_entries_expand_runtime_locations(self):
        entries = self.catalog.iter_entries(self.config)
        by_id = {entry.data_id: entry for entry in entries}

        self.assertIn(0x315, by_id)
        self.assertIn(0x14D6, by_id)
        self.assertIn(0x94900, by_id)
        self.assertGreater(len(entries), 4000)

    def test_unknown_index_remains_readable(self):
        resolution = self.catalog.resolve(0xFFFFF, self.config)

        self.assertFalse(resolution.known)
        self.assertEqual(resolution.name, "未识别索引")


if __name__ == "__main__":
    unittest.main()
