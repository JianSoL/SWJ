"""
Deprecated legacy driver wrapper.

The active runtime driver is `infrastructure/cxcanfd_driver.py`.
This file is kept only as historical reference during migration.
"""

import threading
import time
from ctypes import Structure, c_uint, c_ubyte

from DecodeCanFrame import iDecodeCanFrame
from official_canfd import (
    INVALID_CHANNEL_HANDLE,
    INVALID_DEVICE_HANDLE,
    STATUS_OK,
    TYPE_CAN,
    TYPE_CANFD,
    VCI_USBCANFD,
    OfficialCanFdDevice,
    ZCAN_ReceiveFD_Data,
    ZCAN_Receive_Data,
    ZCAN_TransmitFD_Data,
    ZCAN_Transmit_Data,
)

MAX_RECEIVE_COUNT = 10000
DEFAULT_ARBITRATION_BAUD = 500000
DEFAULT_DATA_BAUD = 2000000
CLOSE_SETTLE_DELAY_SEC = 0.2


class VCI_CAN_OBJ(Structure):
    _fields_ = [
        ("ID", c_uint),
        ("TimeStamp", c_uint),
        ("TimeFlag", c_ubyte),
        ("SendType", c_ubyte),
        ("RemoteFlag", c_ubyte),
        ("ExternFlag", c_ubyte),
        ("DataLen", c_ubyte),
        ("Data", c_ubyte * 8),
        ("Reserved", c_ubyte * 3),
    ]


class Communication:
    def __init__(self, can_type=VCI_USBCANFD, chn=0, ind=0):
        super().__init__()
        self.CanType = can_type
        self.Chn = chn
        self.CanIndex = ind
        self.BaudRate = DEFAULT_ARBITRATION_BAUD
        self.DataBaudRate = DEFAULT_DATA_BAUD
        self.ChannelMode = 0
        self.FDStandard = 0
        self.FilterMode = None
        self.FilterStartID = None
        self.FilterEndID = None
        self.ReceiveTimeoutMs = 10
        self.device_handle = INVALID_DEVICE_HANDLE
        self.channel_handle = INVALID_CHANNEL_HANDLE
        self.driver = OfficialCanFdDevice()
        self.decode = iDecodeCanFrame()
        self.run_flag = False
        self.ReceiveBuffer = (VCI_CAN_OBJ * MAX_RECEIVE_COUNT)()
        self.LastReceiveCanFrames = []
        self.LastReceiveFDFrames = []

    def __del__(self):
        try:
            self.Close()
        except Exception:
            pass

    @staticmethod
    def _normalize_baud_rate(baud_rate):
        if not isinstance(baud_rate, int) or baud_rate <= 0:
            raise ValueError("baud_rate must be a positive integer")
        if baud_rate < 10000:
            return baud_rate * 1000
        return baud_rate

    @staticmethod
    def _trans_can_type(typename):
        if isinstance(typename, int):
            if typename == VCI_USBCANFD:
                return True, typename, "ok"
            return False, 0, f"unsupported CANFD device type: {typename}"

        if not isinstance(typename, str):
            return False, 0, "can_type must be str or int"

        normalized = typename.strip().lower().replace("-", "_")
        aliases = {
            "usbcanfd",
            "usb_canfd",
            "usbcanfd_200u",
            "usbcanfd_200u",
            "usbcanfd_100u",
            "usbcanfd_100u",
            "chuangxin_canfd",
        }
        if normalized in aliases:
            return True, VCI_USBCANFD, "ok"
        return False, 0, f"unsupported CANFD device type: {typename}"

    def set_can_board_configuration(
        self,
        can_type,
        can_idx,
        chn,
        baud_rate,
        data_baud_rate=None,
        fd_standard=0,
        mode=0,
        filter_mode=None,
        filter_start_id=None,
        filter_end_id=None,
        receive_timeout_ms=10,
    ):
        ok, self.CanType, msg = self._trans_can_type(can_type)
        if not ok:
            return False, msg

        if not isinstance(can_idx, int) or can_idx < 0:
            return False, "can_idx must be a non-negative integer"
        if not isinstance(chn, int) or chn < 0:
            return False, "chn must be a non-negative integer"

        self.CanIndex = can_idx
        self.Chn = chn
        self.BaudRate = self._normalize_baud_rate(baud_rate)
        self.DataBaudRate = self._normalize_baud_rate(data_baud_rate if data_baud_rate is not None else baud_rate)
        self.FDStandard = fd_standard
        self.ChannelMode = mode
        self.FilterMode = filter_mode
        self.FilterStartID = filter_start_id
        self.FilterEndID = filter_end_id
        self.ReceiveTimeoutMs = receive_timeout_ms
        return True, "ok"

    def _require_open(self):
        if not self.device_handle or not self.channel_handle:
            raise RuntimeError("CANFD device is not opened")

    def open_new(self):
        if self.device_handle or self.channel_handle:
            self.Close()

        self.device_handle = self.driver.open(device_type=self.CanType, device_index=self.CanIndex, reserved=0)
        self.driver.set_baud(self.Chn, self.BaudRate, self.DataBaudRate)
        self.driver.set_fd_standard(self.Chn, self.FDStandard)
        self.channel_handle = self.driver.init_channel(self.Chn, mode=self.ChannelMode, can_type=TYPE_CANFD)

        if self.FilterMode is not None:
            start_id = 0 if self.FilterStartID is None else self.FilterStartID
            end_id = 0x1FFFFFFF if self.FilterEndID is None else self.FilterEndID
            self.driver.apply_filter(self.channel_handle, self.FilterMode, start_id, end_id)

        self.driver.start_channel(self.channel_handle)

    def Open(self):
        self.open_new()

    def Openx(self):
        self.open_new()

    def _clear_receive_slot(self, index):
        self.ReceiveBuffer[index].ID = 0
        self.ReceiveBuffer[index].TimeStamp = 0
        self.ReceiveBuffer[index].TimeFlag = 0
        self.ReceiveBuffer[index].SendType = 0
        self.ReceiveBuffer[index].RemoteFlag = 0
        self.ReceiveBuffer[index].ExternFlag = 0
        self.ReceiveBuffer[index].DataLen = 0
        for data_index in range(8):
            self.ReceiveBuffer[index].Data[data_index] = 0
        for data_index in range(3):
            self.ReceiveBuffer[index].Reserved[data_index] = 0

    def _copy_can_frame_to_legacy_buffer(self, index, frame, timestamp):
        self._clear_receive_slot(index)
        self.ReceiveBuffer[index].ID = frame.can_id
        self.ReceiveBuffer[index].TimeStamp = int(timestamp & 0xFFFFFFFF)
        self.ReceiveBuffer[index].TimeFlag = 1
        self.ReceiveBuffer[index].RemoteFlag = frame.rtr
        self.ReceiveBuffer[index].ExternFlag = frame.eff
        self.ReceiveBuffer[index].DataLen = min(frame.can_dlc, 8)
        for data_index in range(self.ReceiveBuffer[index].DataLen):
            self.ReceiveBuffer[index].Data[data_index] = frame.data[data_index]

    def _copy_canfd_frame_to_legacy_buffer(self, index, frame, timestamp):
        self._clear_receive_slot(index)
        self.ReceiveBuffer[index].ID = frame.can_id
        self.ReceiveBuffer[index].TimeStamp = int(timestamp & 0xFFFFFFFF)
        self.ReceiveBuffer[index].TimeFlag = 1
        self.ReceiveBuffer[index].RemoteFlag = frame.rtr
        self.ReceiveBuffer[index].ExternFlag = frame.eff
        self.ReceiveBuffer[index].DataLen = min(frame.len, 8)
        for data_index in range(self.ReceiveBuffer[index].DataLen):
            self.ReceiveBuffer[index].Data[data_index] = frame.data[data_index]

    def _record_can_frames(self, receive_buffer, received):
        self.LastReceiveCanFrames = []
        for index in range(received):
            frame = receive_buffer[index].frame
            timestamp = receive_buffer[index].timestamp
            self._copy_can_frame_to_legacy_buffer(index, frame, timestamp)
            self.LastReceiveCanFrames.append(
                {
                    "id": frame.can_id,
                    "len": frame.can_dlc,
                    "timestamp": timestamp,
                    "extern_flag": frame.eff,
                    "remote_flag": frame.rtr,
                    "data": [frame.data[data_index] for data_index in range(frame.can_dlc)],
                }
            )

    def _record_canfd_frames(self, receive_buffer, received):
        self.LastReceiveFDFrames = []
        for index in range(received):
            frame = receive_buffer[index].frame
            timestamp = receive_buffer[index].timestamp
            self._copy_canfd_frame_to_legacy_buffer(index, frame, timestamp)
            self.LastReceiveFDFrames.append(
                {
                    "id": frame.can_id,
                    "len": frame.len,
                    "timestamp": timestamp,
                    "extern_flag": frame.eff,
                    "remote_flag": frame.rtr,
                    "brs": frame.brs,
                    "esi": frame.esi,
                    "data": [frame.data[data_index] for data_index in range(frame.len)],
                }
            )

    def receive_can(self):
        self._require_open()
        pending = self.driver.get_receive_num(self.channel_handle, TYPE_CAN)
        if pending > 0:
            count = min(pending, MAX_RECEIVE_COUNT)
        else:
            # Some devices report 0 pending even though a direct read can still
            # fetch frames. Fall back to a bounded direct poll to match the old
            # driver behaviour more closely.
            count = min(200, MAX_RECEIVE_COUNT)
        received, receive_buffer = self.driver.receive_can(self.channel_handle, count, self.ReceiveTimeoutMs)
        if received <= 0:
            self.LastReceiveCanFrames = []
            return 0

        self._record_can_frames(receive_buffer, received)
        return received

    def receive_canfd(self):
        self._require_open()
        pending = self.driver.get_receive_num(self.channel_handle, TYPE_CANFD)
        if pending > 0:
            count = min(pending, MAX_RECEIVE_COUNT)
        else:
            count = min(200, MAX_RECEIVE_COUNT)
        received, receive_buffer = self.driver.receive_canfd(self.channel_handle, count, self.ReceiveTimeoutMs)
        if received <= 0:
            self.LastReceiveFDFrames = []
            return 0

        self._record_canfd_frames(receive_buffer, received)
        return received

    def _PrintReceiveData(self):
        if not self.channel_handle:
            return 0

        can_count = self.receive_can()
        if can_count > 0:
            return can_count

        canfd_count = self.receive_canfd()
        return canfd_count

    def ReceiveData(self):
        return self._PrintReceiveData()

    def PrintReciveData(self):
        while True:
            self._PrintReceiveData()
            time.sleep(0.1)

    def ReceiveDataAndDecode(self):
        respond = self._PrintReceiveData()
        for index in range(max(respond, 0)):
            self.decode.decode_can_frame_and_store(
                i_d=self.ReceiveBuffer[index].ID,
                dt=self.ReceiveBuffer[index].Data,
            )

    def thread_begin(self):
        self.run_flag = True

    def thread_end(self):
        self.run_flag = False

    def receive(self):
        while True:
            self.ReceiveDataAndDecode()
            time.sleep(0.5)
            print(self.decode.get_decode_msg())

    def Transmit(self, ID, data, remote_flag=False, extern_flag=False, data_len=8):
        self._require_open()

        payload = list(data[:8])
        if len(payload) < 8:
            payload.extend([0] * (8 - len(payload)))

        messages = (ZCAN_Transmit_Data * 1)()
        messages[0].transmit_type = 0
        messages[0].frame.can_id = ID
        messages[0].frame.rtr = 1 if remote_flag else 0
        messages[0].frame.eff = 1 if extern_flag else 0
        messages[0].frame.can_dlc = min(max(data_len, 0), 8)
        for index in range(messages[0].frame.can_dlc):
            messages[0].frame.data[index] = payload[index]

        result = self.driver.transmit_can(self.channel_handle, messages, 1)
        if result != 1:
            print("Transmit CAN frame failed")
        return result

    def TransmitFD(self, ID, data, remote_flag=False, extern_flag=False, brs=True, data_len=None):
        self._require_open()

        payload = list(data[:64])
        actual_len = len(payload) if data_len is None else min(max(data_len, 0), 64)
        if len(payload) < actual_len:
            payload.extend([0] * (actual_len - len(payload)))

        messages = (ZCAN_TransmitFD_Data * 1)()
        messages[0].transmit_type = 0
        messages[0].frame.can_id = ID
        messages[0].frame.rtr = 1 if remote_flag else 0
        messages[0].frame.eff = 1 if extern_flag else 0
        messages[0].frame.brs = 1 if brs else 0
        messages[0].frame.len = actual_len
        for index in range(actual_len):
            messages[0].frame.data[index] = payload[index]

        result = self.driver.transmit_canfd(self.channel_handle, messages, 1)
        if result != 1:
            print("Transmit CANFD frame failed")
        return result

    def Close(self):
        if self.channel_handle:
            time.sleep(CLOSE_SETTLE_DELAY_SEC)
            self.driver.reset_channel(self.channel_handle)
            self.channel_handle = INVALID_CHANNEL_HANDLE
        if self.device_handle:
            self.driver.close()
            self.device_handle = INVALID_DEVICE_HANDLE


class HowToUse:
    def open_it(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usbcanfd", can_idx=0, chn=0, baud_rate=500, data_baud_rate=2000)
        c.open_new()

    def send_frames(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usbcanfd", can_idx=0, chn=0, baud_rate=500, data_baud_rate=2000)
        c.open_new()
        data = [1, 2, 3, 4, 5, 6, 7, 8]
        for _ in range(1000):
            time.sleep(5)
            c.Transmit(0x110, data)

    def send_fd_frames(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usbcanfd", can_idx=0, chn=0, baud_rate=500, data_baud_rate=2000)
        c.open_new()
        data = list(range(16))
        for _ in range(100):
            time.sleep(1)
            c.TransmitFD(0x18FF50E5, data, extern_flag=True, brs=True)

    def close_it(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usbcanfd", can_idx=0, chn=0, baud_rate=500, data_baud_rate=2000)
        c.open_new()
        time.sleep(1)
        c.Close()

    def receive_with_thread(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usbcanfd", can_idx=0, chn=0, baud_rate=500, data_baud_rate=2000)
        c.open_new()
        cycle_read_thread = threading.Thread(target=c.PrintReciveData)
        cycle_read_thread.start()
        while True:
            time.sleep(1)


if __name__ == "__main__":
    helper = HowToUse()
    helper.receive_with_thread()
