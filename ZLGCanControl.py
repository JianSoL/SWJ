import ctypes
from ctypes import (
    POINTER,
    Structure,
    byref,
    c_byte,
    c_int,
    c_ubyte,
    c_uint,
    c_ulong,
    c_void_p,
    pointer,
)
from dataclasses import dataclass
from pathlib import Path
import sys
import threading
import time

from DecodeCanFrame import iDecodeCanFrame


STATUS_OK = 1
RECEIVE_ERR = 0xFFFFFFFF
DEFAULT_BUFFER_SIZE = 10000


class S19Line:
    def __init__(self):
        self.DataType = ""
        self.DataID = ""
        self.DataItem = ""


class VCI_INIT_CONFIG(Structure):
    _fields_ = [
        ("AccCode", c_ulong),
        ("AccMask", c_ulong),
        ("Reserved", c_ulong),
        ("Filter", c_ubyte),
        ("Timing0", c_ubyte),
        ("Timing1", c_ubyte),
        ("Mode", c_ubyte),
    ]


class VCI_CAN_OBJ(Structure):
    _fields_ = [
        ("ID", c_uint),
        ("TimeStamp", c_uint),
        ("TimeFlag", c_byte),
        ("SendType", c_byte),
        ("RemoteFlag", c_byte),
        ("ExternFlag", c_byte),
        ("DataLen", c_ubyte),
        ("Data", c_ubyte * 8),
        ("Reserved", c_ubyte * 3),
    ]


VCI_CAN_OBJ_SEND = VCI_CAN_OBJ


@dataclass
class RawCanFrame:
    frame_id: int
    data: bytes
    extern_flag: bool = False
    remote_flag: bool = False
    timestamp: int = 0

    @property
    def data_len(self):
        return len(self.data)


def _resolve_dll_path():
    current_dir = Path(__file__).resolve().parent
    candidates = [
        Path(sys._MEIPASS) / "ControlCAN.dll" if hasattr(sys, "_MEIPASS") else None,
        current_dir / "ControlCAN.dll",
        Path.cwd() / "ControlCAN.dll",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    raise FileNotFoundError("ControlCAN.dll not found")


def load_control_can_dll():
    dll_obj = ctypes.WinDLL(str(_resolve_dll_path()))
    dll_obj.VCI_OpenDevice.argtypes = (c_ulong, c_ulong, c_ulong)
    dll_obj.VCI_OpenDevice.restype = c_ulong
    dll_obj.VCI_CloseDevice.argtypes = (c_ulong, c_ulong)
    dll_obj.VCI_CloseDevice.restype = c_ulong
    dll_obj.VCI_InitCAN.argtypes = (c_ulong, c_ulong, c_ulong, POINTER(VCI_INIT_CONFIG))
    dll_obj.VCI_InitCAN.restype = c_ulong
    dll_obj.VCI_SetReference.argtypes = (c_ulong, c_ulong, c_ulong, c_ulong, c_void_p)
    dll_obj.VCI_SetReference.restype = c_ulong
    dll_obj.VCI_GetReceiveNum.argtypes = (c_ulong, c_ulong, c_ulong)
    dll_obj.VCI_GetReceiveNum.restype = c_ulong
    dll_obj.VCI_ClearBuffer.argtypes = (c_ulong, c_ulong, c_ulong)
    dll_obj.VCI_ClearBuffer.restype = c_ulong
    dll_obj.VCI_StartCAN.argtypes = (c_ulong, c_ulong, c_ulong)
    dll_obj.VCI_StartCAN.restype = c_ulong
    dll_obj.VCI_ResetCAN.argtypes = (c_ulong, c_ulong, c_ulong)
    dll_obj.VCI_ResetCAN.restype = c_ulong
    dll_obj.VCI_Transmit.argtypes = (c_ulong, c_ulong, c_ulong, POINTER(VCI_CAN_OBJ), c_ulong)
    dll_obj.VCI_Transmit.restype = c_ulong
    dll_obj.VCI_Receive.argtypes = (c_ulong, c_ulong, c_ulong, POINTER(VCI_CAN_OBJ), c_ulong, c_int)
    dll_obj.VCI_Receive.restype = c_ulong
    return dll_obj


dll = load_control_can_dll()


class CanBoardTypeDefines:
    VCI_PCI5121 = 1
    VCI_PCI9810 = 2
    VCI_USBCAN1 = 3
    VCI_USBCAN2 = 4
    VCI_USBCAN2A = 4
    VCI_PCI9820 = 5
    VCI_CAN232 = 6
    VCI_PCI5110 = 7
    VCI_CANLITE = 8
    VCI_ISA9620 = 9
    VCI_ISA5420 = 10
    VCI_PC104CAN = 11
    VCI_CANETUDP = 12
    VCI_CANETE = 12
    VCI_DNP9810 = 13
    VCI_PCI9840 = 14
    VCI_PC104CAN2 = 15
    VCI_PCI9820I = 16
    VCI_CANETTCP = 17
    VCI_PEC9920 = 18
    VCI_PCIE_9220 = 18
    VCI_PCI5010U = 19
    VCI_USBCAN_E_U = 20
    VCI_USBCAN_2E_U = 21
    VCI_PCI5020U = 22
    VCI_EG20T_CAN = 23
    VCI_PCIE9221 = 24
    VCI_WIFICAN_TCP = 25
    VCI_WIFICAN_UDP = 26
    VCI_PCIe9120 = 27
    VCI_PCIe9110 = 28
    VCI_PCIe9140 = 29
    VCI_USBCAN_4E_U = 31
    VCI_CANDTU_200UR = 32
    VCI_CANDTU_MINI = 33
    VCI_USBCAN_8E_U = 34
    VCI_CANREPLAY = 35
    VCI_CANDTU_NET = 36
    VCI_CANDTU_100UR = 37

    group1 = [VCI_USBCAN_2E_U, VCI_USBCAN_E_U, VCI_PCI5010U, VCI_PCI5020U]
    group2 = [VCI_USBCAN_4E_U]


class CanBaudrateDefines:
    def group1_baud_rate(self, baud_rate: int):
        table = {
            1000: 0x060003,
            800: 0x060004,
            500: 0x060007,
            250: 0x1C0008,
            125: 0x1C0011,
            100: 0x160023,
            50: 0x1C002C,
            20: 0x1600B3,
            10: 0x1C00E0,
            5: 0x1C01C1,
        }
        if baud_rate not in table:
            return False, 0, "baud rate is not supported"
        return True, table[baud_rate], "ok"

    def group2_baud_rate(self, baud_rate: int):
        if baud_rate not in {1000, 800, 500, 250, 125, 100, 50, 20, 10, 5}:
            return False, 0, "baud rate is not supported"
        return True, baud_rate * 1000, "ok"

    def get_baud_rate_group_1_2(self, can_type: int, baud_rate: int):
        if can_type in CanBoardTypeDefines.group1:
            return self.group1_baud_rate(baud_rate)
        if can_type in CanBoardTypeDefines.group2:
            return self.group2_baud_rate(baud_rate)
        return False, 0, "can type is not supported by SetReference baud mode"

    def get_baud_rate_group_3(self, baud_rate: int):
        table = {
            10: (0x31, 0x1C),
            20: (0x18, 0x1C),
            40: (0x87, 0xFF),
            50: (0x09, 0x1C),
            80: (0x83, 0xFF),
            100: (0x04, 0x1C),
            125: (0x03, 0x1C),
            200: (0x81, 0xFA),
            250: (0x01, 0x1C),
            400: (0x80, 0xFA),
            500: (0x00, 0x1C),
            666: (0x80, 0xB6),
            800: (0x00, 0x16),
            1000: (0x00, 0x14),
        }
        if baud_rate not in table:
            raise ValueError(f"baud rate is not supported: {baud_rate}")
        return table[baud_rate]


class CanConfigGroup1:
    def __init__(self):
        self.BaudRate = 0
        self.CanType = 0
        self.Chn = 0
        self.CanIndex = 0
        self.init_config = VCI_INIT_CONFIG()


class CanConfigGroup2:
    def __init__(self):
        self.BaudRate = 0
        self.CanType = 0
        self.Chn = 0
        self.CanIndex = 0
        self.init_config = VCI_INIT_CONFIG()


class Communication:
    baud_rate_define = CanBaudrateDefines()

    def __init__(self, can_type=CanBoardTypeDefines.VCI_EG20T_CAN, chn=0, ind=0, dll_obj=None):
        self.dll = dll_obj or dll
        self.BaudRate = 0x060007
        self.CanType = can_type
        self.Chn = chn
        self.CanIndex = ind
        self.config1 = CanConfigGroup1()
        self.config2 = CanConfigGroup2()
        self.decode = iDecodeCanFrame()
        self.ReceiveBuffer = (VCI_CAN_OBJ * DEFAULT_BUFFER_SIZE)()
        self.last_received_frames = []
        self.last_error = ""
        self.is_open = False
        self._device_opened = False
        self.run_flag = False
        self.debug = False
        self._lock = threading.RLock()

    def _error_msg(self, msg: str):
        self.last_error = msg
        return msg

    def _trans_can_type(self, typename):
        if isinstance(typename, int):
            return True, typename, "ok"

        key = str(typename).strip().lower().replace("-", "_")
        aliases = {
            "usb_can_2eu": CanBoardTypeDefines.VCI_USBCAN_2E_U,
            "usb_can_2e_u": CanBoardTypeDefines.VCI_USBCAN_2E_U,
            "usbcan_2eu": CanBoardTypeDefines.VCI_USBCAN_2E_U,
            "usb_can_eu": CanBoardTypeDefines.VCI_USBCAN_E_U,
            "usbcan_eu": CanBoardTypeDefines.VCI_USBCAN_E_U,
            "usb_can_4eu": CanBoardTypeDefines.VCI_USBCAN_4E_U,
            "usb_can_4e_u": CanBoardTypeDefines.VCI_USBCAN_4E_U,
            "usbcan_4eu": CanBoardTypeDefines.VCI_USBCAN_4E_U,
            "usb_can_2": CanBoardTypeDefines.VCI_USBCAN2,
            "usb_can_ii": CanBoardTypeDefines.VCI_USBCAN2,
            "usbcan_ii": CanBoardTypeDefines.VCI_USBCAN2,
            "pci_5010_u": CanBoardTypeDefines.VCI_PCI5010U,
            "pci_5020_u": CanBoardTypeDefines.VCI_PCI5020U,
            "pci_5121": CanBoardTypeDefines.VCI_PCI5121,
            "pci_9810i": CanBoardTypeDefines.VCI_PCI9810,
            "pci_9820": CanBoardTypeDefines.VCI_PCI9820,
            "can_232": CanBoardTypeDefines.VCI_CAN232,
            "can232": CanBoardTypeDefines.VCI_CAN232,
            "pci_5110": CanBoardTypeDefines.VCI_PCI5110,
            "pci5110": CanBoardTypeDefines.VCI_PCI5110,
            "candtu": CanBoardTypeDefines.VCI_CANDTU_MINI,
            "candtu_mini": CanBoardTypeDefines.VCI_CANDTU_MINI,
        }
        if key not in aliases:
            return False, 0, f"unsupported CAN type: {typename}"
        return True, aliases[key], "ok"

    def set_can_board_configuration(self, can_type: str, can_idx: int, chn: int, baud_rate: int):
        if not isinstance(chn, int) or not isinstance(can_idx, int) or not isinstance(baud_rate, int):
            return False, self._error_msg("CAN index, channel and baud rate must be integers")
        if chn < 0 or chn > 7:
            return False, self._error_msg("CAN channel must be in range 0..7")

        stat, resolved_can_type, msg = self._trans_can_type(can_type)
        if not stat:
            return False, self._error_msg(msg)

        self.CanType = resolved_can_type
        self.CanIndex = can_idx
        self.Chn = chn

        if resolved_can_type in CanBoardTypeDefines.group1 or resolved_can_type in CanBoardTypeDefines.group2:
            stat, baud, msg = self.baud_rate_define.get_baud_rate_group_1_2(resolved_can_type, baud_rate)
            if not stat:
                return False, self._error_msg(msg)

            self.config1 = CanConfigGroup1()
            self.config2 = CanConfigGroup2()
            self.config1.CanType = resolved_can_type
            self.config1.CanIndex = can_idx
            self.config1.Chn = chn
            self.config1.BaudRate = baud
            self.config1.init_config = self._build_init_config(baud_rate)
            self.BaudRate = baud
            return True, self._error_msg("ok")

        self.config1 = CanConfigGroup1()
        self.config2 = CanConfigGroup2()
        self.config2.CanType = resolved_can_type
        self.config2.CanIndex = can_idx
        self.config2.Chn = chn
        timing0, timing1 = self.baud_rate_define.get_baud_rate_group_3(baud_rate)
        self.config2.init_config = self._build_init_config(baud_rate, timing0, timing1)
        return True, self._error_msg("ok")

    def Open(self):
        return self.open_new()

    def Openx(self):
        return self.open_new()

    def open_new(self):
        with self._lock:
            config = self._active_config()
            self.close()

            try:
                self._require_status(
                    self.dll.VCI_OpenDevice(config.CanType, config.CanIndex, 0),
                    f"open CAN device failed: type={config.CanType}, index={config.CanIndex}",
                )
                self._device_opened = True

                if config.CanType in CanBoardTypeDefines.group1 or config.CanType in CanBoardTypeDefines.group2:
                    baud = c_int(config.BaudRate)
                    self._require_status(
                        self.dll.VCI_SetReference(
                            config.CanType,
                            config.CanIndex,
                            config.Chn,
                            0,
                            byref(baud),
                        ),
                        f"set CAN baud failed: {config.BaudRate}",
                    )

                self._require_status(
                    self.dll.VCI_InitCAN(
                        config.CanType,
                        config.CanIndex,
                        config.Chn,
                        pointer(config.init_config),
                    ),
                    f"init CAN failed: channel={config.Chn}",
                )
                self._require_status(
                    self.dll.VCI_StartCAN(config.CanType, config.CanIndex, config.Chn),
                    f"start CAN failed: channel={config.Chn}",
                )
                self.dll.VCI_ClearBuffer(config.CanType, config.CanIndex, config.Chn)

                self.CanType = config.CanType
                self.CanIndex = config.CanIndex
                self.Chn = config.Chn
                self.is_open = True
                self.last_error = ""
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self.close()
                raise

    def Close(self):
        return self.close()

    def close(self):
        with self._lock:
            self.run_flag = False
            config = self._active_config(allow_empty=True)
            if config and config.CanType and self._device_opened:
                try:
                    if self.is_open:
                        self.dll.VCI_ResetCAN(config.CanType, config.CanIndex, config.Chn)
                    self.dll.VCI_CloseDevice(config.CanType, config.CanIndex)
                finally:
                    self.is_open = False
                    self._device_opened = False
            else:
                self.is_open = False
            return True

    def clear_buffer(self):
        config = self._active_config()
        self._require_open()
        return self.dll.VCI_ClearBuffer(config.CanType, config.CanIndex, config.Chn)

    def ReceiveData(self):
        return self._receive_and_process(decode=False, bootloader=True)

    def _PrintReceiveData(self, max_count=DEFAULT_BUFFER_SIZE, timeout_ms=10):
        if not self.is_open:
            return 0
        frames = self.receive_frames(max_count=max_count, timeout_ms=timeout_ms)
        return len(frames)

    def PrintReciveData(self):
        self.run_flag = True
        while self.run_flag:
            self._PrintReceiveData()
            time.sleep(0.1)

    def ReceiveDataAndDecode(self):
        return self._receive_and_process(decode=True, bootloader=False)

    def receive_frames(self, max_count=200, timeout_ms=10):
        self._require_open()
        config = self._active_config()
        pending = int(self.dll.VCI_GetReceiveNum(config.CanType, config.CanIndex, config.Chn))
        if pending <= 0 and timeout_ms <= 0:
            self.last_received_frames = []
            return []

        count = min(max(int(max_count), 1), DEFAULT_BUFFER_SIZE)
        if pending > 0:
            count = min(count, pending)

        with self._lock:
            received = self.dll.VCI_Receive(
                config.CanType,
                config.CanIndex,
                config.Chn,
                self.ReceiveBuffer,
                count,
                int(timeout_ms),
            )

        if received == RECEIVE_ERR:
            raise RuntimeError("receive CAN data failed")
        if received <= 0:
            self.last_received_frames = []
            return []

        frames = []
        for index in range(int(received)):
            obj = self.ReceiveBuffer[index]
            data = bytes(obj.Data[: obj.DataLen])
            frames.append(
                RawCanFrame(
                    frame_id=int(obj.ID),
                    data=data,
                    extern_flag=bool(obj.ExternFlag),
                    remote_flag=bool(obj.RemoteFlag),
                    timestamp=int(obj.TimeStamp),
                )
            )
        self.last_received_frames = frames
        return frames

    def thread_begin(self):
        self.run_flag = True

    def thread_end(self):
        self.run_flag = False

    def receive(self):
        self.run_flag = True
        while self.run_flag:
            self.ReceiveDataAndDecode()
            time.sleep(0.05)
            if self.debug:
                print(self.decode.get_decode_msg())

    def printx(self):
        self.run_flag = True
        while self.run_flag:
            print("can thread alive")
            time.sleep(0.1)

    def Transmit(self, ID, data, remote_flag=False, extern_flag=False, data_len=8):
        self._require_open()
        payload = self._normalize_payload(data, data_len)

        frame = VCI_CAN_OBJ_SEND()
        frame.ID = int(ID)
        frame.TimeStamp = 0
        frame.TimeFlag = 0
        frame.SendType = 0
        frame.RemoteFlag = 1 if remote_flag else 0
        frame.ExternFlag = 1 if extern_flag else 0
        frame.DataLen = len(payload)
        frame.Data = (c_ubyte * 8)(*payload, *([0] * (8 - len(payload))))

        config = self._active_config()
        with self._lock:
            result = self.dll.VCI_Transmit(config.CanType, config.CanIndex, config.Chn, pointer(frame), 1)
        if result != 1:
            self.last_error = f"send CAN frame failed: id=0x{int(ID):X}, result={result}"
            if self.debug:
                print(self.last_error)
        return int(result)

    def TranExtentedSession(self):
        data = (0x02, 0x10, 0x03, 0, 0, 0, 0, 0)
        return self.Transmit(self.m_SendID, data)

    def TimeHandle(self, msg):
        pass

    def RoutineSend(self):
        while self.run_flag:
            self.m_ReturnResult[self._MessageName.ReturnConstantMessage.value] = False
            self.SendConstantCommand()
            start_time = time.perf_counter()
            while self.m_ReturnResult[self._MessageName.ReturnConstantMessage.value] is not True:
                if (time.perf_counter() - start_time) > 1:
                    print("keep-alive failed")
                    return
                time.sleep(0.01)
            if self.debug:
                print("keep-alive ok")
            time.sleep(2)

    def _receive_and_process(self, decode=False, bootloader=False):
        frames = self.receive_frames(max_count=DEFAULT_BUFFER_SIZE, timeout_ms=10)
        if decode:
            for frame in frames:
                self.decode.decode_can_frame_and_store(i_d=frame.frame_id, dt=frame.data)

        if bootloader:
            for index, frame in enumerate(frames):
                if frame.frame_id == (self.m_AdrReceiveID + 0):
                    data = self.ReceiveBuffer[index].Data
                    self.GetLengthOfBlock(data)
                    self.CheckIsBlockWriterOver(data)
                    for item_index, item in enumerate(self.m_ReturnData):
                        if self.CheckIsReturn(item, data):
                            self.m_ReturnResult[item_index] = True
        return len(frames)

    def _active_config(self, allow_empty=False):
        if self.config1.CanType:
            return self.config1
        if self.config2.CanType:
            return self.config2
        if allow_empty:
            return None
        raise RuntimeError("CAN configuration is not set")

    def _require_open(self):
        if not self.is_open:
            raise RuntimeError("CAN device is not opened")

    def _require_status(self, result, message):
        if result != STATUS_OK:
            raise RuntimeError(message)

    @staticmethod
    def _build_init_config(baud_rate, timing0=None, timing1=None):
        init_config = VCI_INIT_CONFIG()
        init_config.AccCode = 0x00000000
        init_config.AccMask = 0xFFFFFFFF
        init_config.Reserved = 0
        init_config.Filter = 1
        if timing0 is None or timing1 is None:
            timing0, timing1 = CanBaudrateDefines().get_baud_rate_group_3(baud_rate)
        init_config.Timing0 = timing0
        init_config.Timing1 = timing1
        init_config.Mode = 0
        return init_config

    @staticmethod
    def _normalize_payload(data, data_len):
        if data is None:
            values = []
        elif isinstance(data, (bytes, bytearray)):
            values = list(data)
        else:
            values = [int(value) for value in data]

        if data_len is None:
            data_len = len(values)
        data_len = max(0, min(int(data_len), 8))
        if len(values) < data_len:
            values.extend([0] * (data_len - len(values)))
        values = values[:data_len]

        for value in values:
            if value < 0 or value > 0xFF:
                raise ValueError(f"CAN payload byte out of range: {value}")
        return values


class HowToUse:
    def open_it(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usb_can_2eu", can_idx=0, chn=1, baud_rate=500)
        c.open_new()
        c.Close()

    def send_frames(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usb_can_2eu", can_idx=0, chn=1, baud_rate=500)
        c.open_new()
        try:
            data = [1, 2, 3, 4, 5, 6, 7, 8]
            for _ in range(1000):
                time.sleep(5)
                c.Transmit(0x110, data)
        finally:
            c.Close()

    def send_extend_frames(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usb_can_2eu", can_idx=0, chn=1, baud_rate=500)
        c.open_new()
        try:
            data = [1, 2, 3, 4, 5, 6]
            for _ in range(500):
                c.Transmit(0x212, data, data_len=7)
        finally:
            c.Close()

    def close_it(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usb_can_2eu", can_idx=0, chn=1, baud_rate=500)
        c.open_new()
        time.sleep(10)
        c.Close()

    def receive_with_thread(self):
        c = Communication()
        c.set_can_board_configuration(can_type="usb_can_2eu", can_idx=0, chn=1, baud_rate=500)
        c.open_new()
        cycle_read_thread = threading.Thread(target=c.PrintReciveData, daemon=True)
        cycle_read_thread.start()
        try:
            while True:
                time.sleep(1)
        finally:
            c.thread_end()
            c.Close()


if __name__ == "__main__":
    HowToUse().receive_with_thread()
