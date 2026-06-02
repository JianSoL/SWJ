from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BusConfig:
    can_type: int
    device_index: int
    channel_index: int
    arbitration_baud: int
    data_baud: int
    fd_standard: int = 0
    mode: int = 0
    receive_timeout_ms: int = 10
    filter_mode: Optional[int] = None
    filter_start_id: Optional[int] = None
    filter_end_id: Optional[int] = None


@dataclass
class RawFrame:
    frame_id: int
    data: bytes
    is_fd: bool
    extern_flag: bool
    remote_flag: bool
    timestamp: int = 0
    brs: bool = False
    esi: bool = False

    @property
    def data_len(self):
        return len(self.data)


@dataclass
class LegacySignalDefinition:
    signal_id: int
    name: str
    unit: str
    table_index: int
    row_index: int
    bit_start: int
    bit_length: int
    signed: bool
    save_to_log: bool


@dataclass
class LegacySignalUpdate:
    cluster_index: int
    signal_id: int
    signal_name: str
    value: str
    unit: str
    table_index: int
    row_index: int
    source_kind: str


@dataclass
class PeriodicSignalUpdate:
    address: str
    row_key: str
    message_name: str
    signal_name: str
    value: str
    unit: str


@dataclass
class PollResult:
    legacy_updates: List[LegacySignalUpdate] = field(default_factory=list)
    periodic_updates: List[PeriodicSignalUpdate] = field(default_factory=list)
    periodic_status: Dict[str, str] = field(default_factory=dict)
    balance_updates: List[str] = field(default_factory=list)
    had_rx_frame: bool = False


@dataclass(frozen=True)
class AlarmParameterField:
    key: str
    label: str
    index: int
    signed: bool = False
    summary: bool = False


@dataclass(frozen=True)
class AlarmParameterDefinition:
    alarm_id: int
    code: str
    name: str


@dataclass
class AlarmParameterRecord:
    alarm_id: int
    code: str
    name: str
    values: Dict[str, int] = field(default_factory=dict)
    is_complete: bool = True
