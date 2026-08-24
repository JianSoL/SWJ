from ctypes import (
    Structure,
    Union,
    WinDLL,
    byref,
    c_long,
    c_uint,
    c_ulong,
    c_ulonglong,
    c_ubyte,
    c_ushort,
    c_void_p,
)
from pathlib import Path
import sys

from domain.models import BusConfig, RawFrame


STATUS_OK = 1
INVALID_DEVICE_HANDLE = 0
INVALID_CHANNEL_HANDLE = 0
TYPE_CAN = 0
TYPE_CANFD = 1
VCI_USBCAN2 = 41


class _ZCAN_CHANNEL_CAN_INIT_CONFIG(Structure):
    _fields_ = [
        ("acc_code", c_uint),
        ("acc_mask", c_uint),
        ("reserved", c_uint),
        ("filter", c_ubyte),
        ("timing0", c_ubyte),
        ("timing1", c_ubyte),
        ("mode", c_ubyte),
    ]


class _ZCAN_CHANNEL_CANFD_INIT_CONFIG(Structure):
    _fields_ = [
        ("acc_code", c_uint),
        ("acc_mask", c_uint),
        ("abit_timing", c_uint),
        ("dbit_timing", c_uint),
        ("brp", c_uint),
        ("filter", c_ubyte),
        ("mode", c_ubyte),
        ("pad", c_ushort),
        ("reserved", c_uint),
    ]


class _ZCAN_CHANNEL_INIT_CONFIG(Union):
    _fields_ = [
        ("can", _ZCAN_CHANNEL_CAN_INIT_CONFIG),
        ("canfd", _ZCAN_CHANNEL_CANFD_INIT_CONFIG),
    ]


class ZCAN_CHANNEL_INIT_CONFIG(Structure):
    _fields_ = [("can_type", c_uint), ("config", _ZCAN_CHANNEL_INIT_CONFIG)]


class ZCAN_CAN_FRAME(Structure):
    _fields_ = [
        ("can_id", c_uint, 29),
        ("err", c_uint, 1),
        ("rtr", c_uint, 1),
        ("eff", c_uint, 1),
        ("can_dlc", c_ubyte),
        ("__pad", c_ubyte),
        ("__res0", c_ubyte),
        ("__res1", c_ubyte),
        ("data", c_ubyte * 8),
    ]


class ZCAN_CANFD_FRAME(Structure):
    _fields_ = [
        ("can_id", c_uint, 29),
        ("err", c_uint, 1),
        ("rtr", c_uint, 1),
        ("eff", c_uint, 1),
        ("len", c_ubyte),
        ("brs", c_ubyte, 1),
        ("esi", c_ubyte, 1),
        ("__res", c_ubyte, 6),
        ("__res0", c_ubyte),
        ("__res1", c_ubyte),
        ("data", c_ubyte * 64),
    ]


class ZCAN_Transmit_Data(Structure):
    _fields_ = [("frame", ZCAN_CAN_FRAME), ("transmit_type", c_uint)]


class ZCAN_Receive_Data(Structure):
    _fields_ = [("frame", ZCAN_CAN_FRAME), ("timestamp", c_ulonglong)]


class ZCAN_TransmitFD_Data(Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("transmit_type", c_uint)]


class ZCAN_ReceiveFD_Data(Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("timestamp", c_ulonglong)]


def _resolve_dll_path():
    current_dir = Path(__file__).resolve().parent
    candidates = [
        Path(sys._MEIPASS) / "ControlCANFD.dll"
        if hasattr(sys, "_MEIPASS")
        else None,
        current_dir.parent / "ControlCANFD.dll",
        current_dir.parent.parent / "ControlCANFD.dll",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    raise FileNotFoundError("ControlCANFD.dll not found")


def load_canfd_dll():
    dll = WinDLL(str(_resolve_dll_path()))
    dll.ZCAN_OpenDevice.restype = c_void_p
    dll.ZCAN_SetAbitBaud.argtypes = (c_void_p, c_ulong, c_ulong)
    dll.ZCAN_SetDbitBaud.argtypes = (c_void_p, c_ulong, c_ulong)
    dll.ZCAN_SetCANFDStandard.argtypes = (c_void_p, c_ulong, c_ulong)
    dll.ZCAN_InitCAN.argtypes = (c_void_p, c_ulong, c_void_p)
    dll.ZCAN_InitCAN.restype = c_void_p
    dll.ZCAN_StartCAN.argtypes = (c_void_p,)
    dll.ZCAN_Transmit.argtypes = (c_void_p, c_void_p, c_ulong)
    dll.ZCAN_TransmitFD.argtypes = (c_void_p, c_void_p, c_ulong)
    dll.ZCAN_GetReceiveNum.argtypes = (c_void_p, c_ulong)
    dll.ZCAN_Receive.argtypes = (c_void_p, c_void_p, c_ulong, c_long)
    dll.ZCAN_ReceiveFD.argtypes = (c_void_p, c_void_p, c_ulong, c_long)
    dll.ZCAN_ResetCAN.argtypes = (c_void_p,)
    dll.ZCAN_CloseDevice.argtypes = (c_void_p,)
    dll.ZCAN_ClearFilter.argtypes = (c_void_p,)
    dll.ZCAN_AckFilter.argtypes = (c_void_p,)
    dll.ZCAN_SetFilterMode.argtypes = (c_void_p, c_ulong)
    dll.ZCAN_SetFilterStartID.argtypes = (c_void_p, c_ulong)
    dll.ZCAN_SetFilterEndID.argtypes = (c_void_p, c_ulong)
    return dll


class CxCanFdDriver:
    def __init__(self, dll=None):
        self.dll = dll or load_canfd_dll()
        self.device_handle = INVALID_DEVICE_HANDLE
        self.channel_handle = INVALID_CHANNEL_HANDLE
        self.config = None
        self._can_receive_buffer = None
        self._can_receive_capacity = 0
        self._canfd_receive_buffer = None
        self._canfd_receive_capacity = 0

    def open(self, config):
        self.close()
        self.config = config
        try:
            self.device_handle = self.dll.ZCAN_OpenDevice(config.can_type, config.device_index, 0)
            if not self.device_handle:
                raise RuntimeError("Open CANFD device failed")

            self._require_status(
                self.dll.ZCAN_SetAbitBaud(
                    self.device_handle,
                    config.channel_index,
                    config.arbitration_baud,
                ),
                "Set arbitration baud failed",
            )
            self._require_status(
                self.dll.ZCAN_SetDbitBaud(
                    self.device_handle,
                    config.channel_index,
                    config.data_baud,
                ),
                "Set data baud failed",
            )
            self._require_status(
                self.dll.ZCAN_SetCANFDStandard(
                    self.device_handle,
                    config.channel_index,
                    config.fd_standard,
                ),
                "Set CANFD standard failed",
            )

            init_config = ZCAN_CHANNEL_INIT_CONFIG()
            init_config.can_type = TYPE_CANFD
            init_config.config.canfd.mode = config.mode
            self.channel_handle = self.dll.ZCAN_InitCAN(
                self.device_handle,
                config.channel_index,
                byref(init_config),
            )
            if not self.channel_handle:
                raise RuntimeError("Init CAN channel failed")

            if config.filter_mode is not None:
                self.dll.ZCAN_ClearFilter(self.channel_handle)
                self.dll.ZCAN_SetFilterMode(self.channel_handle, config.filter_mode)
                self.dll.ZCAN_SetFilterStartID(self.channel_handle, config.filter_start_id or 0)
                self.dll.ZCAN_SetFilterEndID(self.channel_handle, config.filter_end_id or 0x1FFFFFFF)
                self.dll.ZCAN_AckFilter(self.channel_handle)

            self._require_status(
                self.dll.ZCAN_StartCAN(self.channel_handle),
                "Start CAN channel failed",
            )
        except Exception:
            self.close()
            raise

    def close(self):
        if self.channel_handle:
            self.dll.ZCAN_ResetCAN(self.channel_handle)
            self.channel_handle = INVALID_CHANNEL_HANDLE
        if self.device_handle:
            self.dll.ZCAN_CloseDevice(self.device_handle)
            self.device_handle = INVALID_DEVICE_HANDLE

    def send_can(self, frame):
        self._require_open()
        messages = (ZCAN_Transmit_Data * 1)()
        messages[0].transmit_type = 0
        messages[0].frame.can_id = frame.frame_id
        messages[0].frame.eff = 1 if frame.extern_flag else 0
        messages[0].frame.rtr = 1 if frame.remote_flag else 0
        messages[0].frame.can_dlc = min(frame.data_len, 8)
        for index in range(messages[0].frame.can_dlc):
            messages[0].frame.data[index] = frame.data[index]
        return self.dll.ZCAN_Transmit(self.channel_handle, messages, 1)

    def send_canfd(self, frame):
        self._require_open()
        messages = (ZCAN_TransmitFD_Data * 1)()
        messages[0].transmit_type = 0
        messages[0].frame.can_id = frame.frame_id
        messages[0].frame.eff = 1 if frame.extern_flag else 0
        messages[0].frame.rtr = 1 if frame.remote_flag else 0
        messages[0].frame.brs = 1 if frame.brs else 0
        messages[0].frame.len = min(frame.data_len, 64)
        for index in range(messages[0].frame.len):
            messages[0].frame.data[index] = frame.data[index]
        return self.dll.ZCAN_TransmitFD(self.channel_handle, messages, 1)

    def receive_can(self, max_count=200, timeout_ms=None):
        return self._receive(frame_type=TYPE_CAN, max_count=max_count, timeout_ms=timeout_ms)

    def receive_canfd(self, max_count=200, timeout_ms=None):
        return self._receive(frame_type=TYPE_CANFD, max_count=max_count, timeout_ms=timeout_ms)

    def _receive(self, frame_type, max_count, timeout_ms):
        self._require_open()
        timeout = self.config.receive_timeout_ms if timeout_ms is None else timeout_ms
        pending = self.dll.ZCAN_GetReceiveNum(self.channel_handle, frame_type)
        if pending <= 0 and timeout <= 0:
            return []
        count = 1 if pending <= 0 else min(int(pending), max_count)
        if frame_type == TYPE_CAN:
            return self._receive_can_frames(count, timeout)
        return self._receive_canfd_frames(count, timeout)

    def _receive_can_frames(self, count, timeout_ms):
        receive_buffer = self._get_receive_buffer(TYPE_CAN, count)
        received = self.dll.ZCAN_Receive(self.channel_handle, byref(receive_buffer), count, timeout_ms)
        frames = []
        for index in range(max(received, 0)):
            frame = receive_buffer[index].frame
            frames.append(
                RawFrame(
                    frame_id=frame.can_id,
                    data=bytes(frame.data[: frame.can_dlc]),
                    is_fd=False,
                    extern_flag=bool(frame.eff),
                    remote_flag=bool(frame.rtr),
                    timestamp=receive_buffer[index].timestamp,
                )
            )
        return frames

    def _receive_canfd_frames(self, count, timeout_ms):
        receive_buffer = self._get_receive_buffer(TYPE_CANFD, count)
        received = self.dll.ZCAN_ReceiveFD(self.channel_handle, byref(receive_buffer), count, timeout_ms)
        frames = []
        for index in range(max(received, 0)):
            frame = receive_buffer[index].frame
            frames.append(
                RawFrame(
                    frame_id=frame.can_id,
                    data=bytes(frame.data[: frame.len]),
                    is_fd=True,
                    extern_flag=bool(frame.eff),
                    remote_flag=bool(frame.rtr),
                    timestamp=receive_buffer[index].timestamp,
                    brs=bool(frame.brs),
                    esi=bool(frame.esi),
                )
            )
        return frames

    def _get_receive_buffer(self, frame_type, count):
        if frame_type == TYPE_CAN:
            if self._can_receive_capacity < count:
                self._can_receive_buffer = (ZCAN_Receive_Data * count)()
                self._can_receive_capacity = count
            return self._can_receive_buffer

        if self._canfd_receive_capacity < count:
            self._canfd_receive_buffer = (ZCAN_ReceiveFD_Data * count)()
            self._canfd_receive_capacity = count
        return self._canfd_receive_buffer

    def _require_open(self):
        if not self.device_handle or not self.channel_handle:
            raise RuntimeError("CANFD device is not opened")

    @staticmethod
    def _require_status(result, message):
        if result != STATUS_OK:
            raise RuntimeError(message)
