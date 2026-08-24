import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.device_service import DeviceService
from domain.models import PollResult


class DeviceServiceTests(unittest.TestCase):
    def setUp(self):
        self.protocol_service = MagicMock()
        self.protocol_service.cluster_indices = [0, 1]
        self.protocol_service.cluster_addresses = ["00", "A0"]
        self.protocol_service.snapshot_logging_enabled = True
        self.dashboard_service = MagicMock()
        self.service = DeviceService(
            self.protocol_service,
            self.dashboard_service,
        )

    def test_poll_updates_dashboard_after_protocol_poll(self):
        poll_result = PollResult(had_rx_frame=True)
        self.protocol_service.poll.return_value = poll_result

        result = self.service.poll()

        self.assertIs(result, poll_result)
        self.dashboard_service.ingest_poll_result.assert_called_once_with(poll_result)

    def test_runtime_reconfiguration_rebuilds_dashboard_state(self):
        updates = {"BCU_NUM": 4, "ADDRESLIST": ["00", "A0", "A1", "A2"]}
        self.protocol_service.update_runtime_config.return_value = True

        result = self.service.update_runtime_config(updates)

        self.assertTrue(result)
        self.protocol_service.update_runtime_config.assert_called_once_with(updates)
        self.dashboard_service.reconfigure.assert_called_once_with()

    def test_legacy_methods_are_available_during_gradual_migration(self):
        self.protocol_service.send_signal_query.return_value = 1

        result = self.service.send_signal_query(1, 0x10)

        self.assertEqual(result, 1)
        self.protocol_service.send_signal_query.assert_called_once_with(1, 0x10)


if __name__ == "__main__":
    unittest.main()
