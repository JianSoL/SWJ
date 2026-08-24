import math
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.trend_store import TrendDataStore, aggregate_period_statistics


class TrendStoreTests(unittest.TestCase):
    def test_aggregate_period_statistics_builds_ohlc_bars(self):
        bars = aggregate_period_statistics(
            [(1.0, 10.0), (2.0, 12.0), (4.9, 8.0), (5.1, 11.0)],
            period_seconds=5,
        )

        self.assertEqual(len(bars), 2)
        self.assertEqual(
            (bars[0].first, bars[0].maximum, bars[0].minimum, bars[0].latest),
            (10.0, 12.0, 8.0, 8.0),
        )
        self.assertEqual(bars[0].sample_count, 3)
        self.assertEqual(bars[1].latest, 11.0)

    def test_store_updates_all_periods_and_bounds_memory(self):
        store = TrendDataStore(periods=(1, 5), max_bars_per_period=2)
        for timestamp, value in ((0.0, 10.0), (1.0, 11.0), (2.0, 12.0)):
            self.assertTrue(store.add_sample(1, "voltage", value, timestamp))

        one_second_bars = store.bars_for(1, "voltage", 1)
        five_second_bars = store.bars_for(1, "voltage", 5)
        self.assertEqual([bar.latest for bar in one_second_bars], [11.0, 12.0])
        self.assertEqual(len(five_second_bars), 1)
        self.assertEqual(five_second_bars[0].sample_count, 3)
        self.assertEqual(store.sample_count(1, "voltage"), 3)
        self.assertEqual(store.latest_value(1, "voltage"), 12.0)

    def test_store_rejects_invalid_samples_and_clears_cluster(self):
        store = TrendDataStore()
        self.assertFalse(store.add_sample(0, "voltage", 1, 1))
        self.assertFalse(store.add_sample(1, "unknown", 1, 1))
        self.assertFalse(store.add_sample(1, "hall_current", math.nan, 1))
        self.assertTrue(store.add_sample(2, "shunt_current", -12.5, 10))
        store.clear_cluster(2)
        self.assertEqual(store.sample_count(2, "shunt_current"), 0)


if __name__ == "__main__":
    unittest.main()
