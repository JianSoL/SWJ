"""
Deprecated reference module.

The active runtime driver is `infrastructure/cxcanfd_driver.py`, which keeps the
same DLL call sequence as the official `cxcanfd_x64_v2.0.py` sample but isolates
all device access inside the infrastructure layer.
"""

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
import time

STATUS_OK = 1
INVALID_DEVICE_HANDLE = 0
INVALID_CHANNEL_HANDLE = 0

TYPE_CAN = 0
TYPE_CANFD = 1

VCI_USBCANFD = 41
OPEN_RETRY_COUNT = 5
OPEN_RETRY_DELAY_SEC = 0.2


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
        current_dir / "ControlCANFD.dll",
        current_dir.parent / "ControlCANFD.dll",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("ControlCANFD.dll not found in CANFD directory or project root.")


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


class OfficialCanFdDevice:
    def __init__(self):
        self.dll = load_canfd_dll()
        self.device_handle = INVALID_DEVICE_HANDLE

    def open(self, device_type=VCI_USBCANFD, device_index=0, reserved=0):
        self.device_handle = INVALID_DEVICE_HANDLE
        for _ in range(OPEN_RETRY_COUNT):
            self.device_handle = self.dll.ZCAN_OpenDevice(device_type, device_index, reserved)
            if self.device_handle:
                return self.device_handle
            time.sleep(OPEN_RETRY_DELAY_SEC)

        raise RuntimeError(
            "Open CANFD device failed. Check whether the adapter is connected, "
            "the WinUSB driver is installed, and no other CAN tool is occupying the device."
        )

    def ensure_open(self):
        if not self.device_handle:
            raise RuntimeError("CANFD device is not opened")

    def set_baud(self, channel, arbitration_baud, data_baud):
        self.ensure_open()
        if self.dll.ZCAN_SetAbitBaud(self.device_handle, channel, arbitration_baud) != STATUS_OK:
            raise RuntimeError(f"Set CAN{channel} arbitration baud failed: {arbitration_baud}")
        if self.dll.ZCAN_SetDbitBaud(self.device_handle, channel, data_baud) != STATUS_OK:
            raise RuntimeError(f"Set CAN{channel} data baud failed: {data_baud}")

    def set_fd_standard(self, channel, fd_standard=0):
        self.ensure_open()
        if self.dll.ZCAN_SetCANFDStandard(self.device_handle, channel, fd_standard) != STATUS_OK:
            raise RuntimeError(f"Set CAN{channel} CANFD standard failed: {fd_standard}")

    def init_channel(self, channel, mode=0, can_type=TYPE_CANFD):
        self.ensure_open()
        init_config = ZCAN_CHANNEL_INIT_CONFIG()
        init_config.can_type = can_type
        init_config.config.canfd.mode = mode
        channel_handle = self.dll.ZCAN_InitCAN(self.device_handle, channel, byref(init_config))
        if not channel_handle:
            raise RuntimeError(f"Init CAN{channel} failed")
        return channel_handle

    def apply_filter(self, channel_handle, filter_mode, start_id, end_id):
        self.dll.ZCAN_ClearFilter(channel_handle)
        self.dll.ZCAN_SetFilterMode(channel_handle, filter_mode)
        self.dll.ZCAN_SetFilterStartID(channel_handle, start_id)
        self.dll.ZCAN_SetFilterEndID(channel_handle, end_id)
        self.dll.ZCAN_AckFilter(channel_handle)

    def start_channel(self, channel_handle):
        if self.dll.ZCAN_StartCAN(channel_handle) != STATUS_OK:
            raise RuntimeError("Start CANFD channel failed")

    def transmit_can(self, channel_handle, frames, count):
        return self.dll.ZCAN_Transmit(channel_handle, frames, count)

    def transmit_canfd(self, channel_handle, frames, count):
        return self.dll.ZCAN_TransmitFD(channel_handle, frames, count)

    def get_receive_num(self, channel_handle, frame_type):
        return self.dll.ZCAN_GetReceiveNum(channel_handle, frame_type)

    def receive_can(self, channel_handle, count, timeout_ms):
        receive_buffer = (ZCAN_Receive_Data * count)()
        received = self.dll.ZCAN_Receive(channel_handle, byref(receive_buffer), count, timeout_ms)
        return received, receive_buffer

    def receive_canfd(self, channel_handle, count, timeout_ms):
        receive_buffer = (ZCAN_ReceiveFD_Data * count)()
        received = self.dll.ZCAN_ReceiveFD(channel_handle, byref(receive_buffer), count, timeout_ms)
        return received, receive_buffer

    def reset_channel(self, channel_handle):
        return self.dll.ZCAN_ResetCAN(channel_handle)

    def close(self):
        if self.device_handle:
            result = self.dll.ZCAN_CloseDevice(self.device_handle)
            self.device_handle = INVALID_DEVICE_HANDLE
            return result
        return STATUS_OK
