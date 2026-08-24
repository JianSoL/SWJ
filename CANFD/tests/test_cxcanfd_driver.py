import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from domain.models import BusConfig, RawFrame
from infrastructure.cxcanfd_driver import CxCanFdDriver, STATUS_OK, TYPE_CAN, TYPE_CANFD, VCI_USBCAN2


class FakeDll:
    def __init__(self):
        self.open_calls = []
        self.transmit_calls = []
        self.receive_can_calls = 0
        self.receive_canfd_calls = 0
        self.receive_num = 1
        self.receive_can_args = []
        self.receive_canfd_args = []
        self.reset_calls = 0
        self.close_calls = 0
        self.start_result = STATUS_OK

    def ZCAN_OpenDevice(self, device_type, device_index, reserved):
        self.open_calls.append((device_type, device_index, reserved))
        return 0x11

    def ZCAN_SetAbitBaud(self, device_handle, channel, baud):
        return STATUS_OK

    def ZCAN_SetDbitBaud(self, device_handle, channel, baud):
        return STATUS_OK

    def ZCAN_SetCANFDStandard(self, device_handle, channel, standard):
        return STATUS_OK

    def ZCAN_InitCAN(self, device_handle, channel, config_ref):
        self.init_can_type = config_ref._obj.can_type
        return 0x22

    def ZCAN_StartCAN(self, channel_handle):
        return self.start_result

    def ZCAN_Transmit(self, channel_handle, messages, count):
        self.transmit_calls.append(("can", messages[0].frame.can_id, messages[0].frame.can_dlc))
        return count

    def ZCAN_TransmitFD(self, channel_handle, messages, count):
        self.transmit_calls.append(("canfd", messages[0].frame.can_id, messages[0].frame.len))
        return count

    def ZCAN_GetReceiveNum(self, channel_handle, frame_type):
        return self.receive_num

    def ZCAN_Receive(self, channel_handle, buffer_ref, count, timeout_ms):
        self.receive_can_calls += 1
        self.receive_can_args.append((count, timeout_ms))
        buffer_ref._obj[0].frame.can_id = 0x1881F2A0
        buffer_ref._obj[0].frame.eff = 1
        buffer_ref._obj[0].frame.can_dlc = 8
        for index, value in enumerate([1, 2, 3, 4, 5, 6, 7, 8]):
            buffer_ref._obj[0].frame.data[index] = value
        buffer_ref._obj[0].timestamp = 123
        return 1

    def ZCAN_ReceiveFD(self, channel_handle, buffer_ref, count, timeout_ms):
        self.receive_canfd_calls += 1
        self.receive_canfd_args.append((count, timeout_ms))
        buffer_ref._obj[0].frame.can_id = 0x1201EF00
        buffer_ref._obj[0].frame.eff = 1
        buffer_ref._obj[0].frame.len = 8
        buffer_ref._obj[0].frame.brs = 1
        for index, value in enumerate([9, 8, 7, 6, 5, 4, 3, 2]):
            buffer_ref._obj[0].frame.data[index] = value
        buffer_ref._obj[0].timestamp = 456
        return 1

    def ZCAN_ResetCAN(self, channel_handle):
        self.reset_calls += 1
        return STATUS_OK

    def ZCAN_CloseDevice(self, device_handle):
        self.close_calls += 1
        return STATUS_OK

    def ZCAN_ClearFilter(self, channel_handle):
        return STATUS_OK

    def ZCAN_AckFilter(self, channel_handle):
        return STATUS_OK

    def ZCAN_SetFilterMode(self, channel_handle, filter_mode):
        return STATUS_OK

    def ZCAN_SetFilterStartID(self, channel_handle, start_id):
        return STATUS_OK

    def ZCAN_SetFilterEndID(self, channel_handle, end_id):
        return STATUS_OK


class CxCanFdDriverTests(unittest.TestCase):
    def setUp(self):
        self.fake_dll = FakeDll()
        self.driver = CxCanFdDriver(dll=self.fake_dll)
        self.config = BusConfig(
            can_type=VCI_USBCAN2,
            device_index=0,
            channel_index=0,
            arbitration_baud=500000,
            data_baud=2000000,
        )

    def test_open_send_receive_and_close(self):
        self.driver.open(self.config)
        self.assertEqual(self.fake_dll.open_calls[0][0], VCI_USBCAN2)

        send_result = self.driver.send_can(
            RawFrame(
                frame_id=0x1880A0F2,
                data=b"\x01\x02\x03\x04\x05\x06\x07\x08",
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )
        self.assertEqual(send_result, 1)

        can_frames = self.driver.receive_can(max_count=5)
        canfd_frames = self.driver.receive_canfd(max_count=5)
        self.assertEqual(can_frames[0].frame_id, 0x1881F2A0)
        self.assertEqual(canfd_frames[0].frame_id, 0x1201EF00)
        self.assertEqual(canfd_frames[0].data, bytes([9, 8, 7, 6, 5, 4, 3, 2]))

        self.driver.close()

    def test_receive_skips_nonblocking_read_when_idle(self):
        self.config.receive_timeout_ms = 0
        self.fake_dll.receive_num = 0
        self.driver.open(self.config)

        self.assertEqual(self.driver.receive_can(max_count=5), [])
        self.assertEqual(self.driver.receive_canfd(max_count=5), [])

        self.assertEqual(self.fake_dll.receive_can_calls, 0)
        self.assertEqual(self.fake_dll.receive_canfd_calls, 0)

    def test_receive_reuses_allocated_ctypes_buffers(self):
        self.driver.open(self.config)

        self.driver.receive_can(max_count=5)
        can_buffer = self.driver._can_receive_buffer
        self.driver.receive_can(max_count=5)

        self.driver.receive_canfd(max_count=5)
        canfd_buffer = self.driver._canfd_receive_buffer
        self.driver.receive_canfd(max_count=5)

        self.assertIs(self.driver._can_receive_buffer, can_buffer)
        self.assertIs(self.driver._canfd_receive_buffer, canfd_buffer)

    def test_open_failure_closes_partial_handles(self):
        self.fake_dll.start_result = 0

        with self.assertRaisesRegex(RuntimeError, "Start CAN channel failed"):
            self.driver.open(self.config)

        self.assertEqual(self.fake_dll.reset_calls, 1)
        self.assertEqual(self.fake_dll.close_calls, 1)
        self.assertEqual(self.driver.device_handle, 0)
        self.assertEqual(self.driver.channel_handle, 0)


if __name__ == "__main__":
    unittest.main()
