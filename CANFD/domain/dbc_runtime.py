import re
from dataclasses import dataclass, field
from typing import Dict, List


MESSAGE_RE = re.compile(r"^BO_\s+(?P<raw_id>\d+)\s+(?P<name>\S+):\s+(?P<dlc>\d+)\s+\S+")
SIGNAL_RE = re.compile(
    r'^ SG_\s+(?P<name>\S+)(?:\s+\S+)?\s*:\s*'
    r'(?P<start>\d+)\|(?P<length>\d+)@(?P<byte_order>[01])(?P<signed>[+-])\s*'
    r'\((?P<factor>[^,]+),(?P<offset>[^\)]+)\)\s*'
    r'\[(?P<minimum>[^|]+)\|(?P<maximum>[^\]]+)\]\s*'
    r'"(?P<unit>[^"]*)"\s+\S+'
)


@dataclass
class SignalDefinition:
    name: str
    start_bit: int
    bit_length: int
    is_signed: bool
    factor: float
    offset: float
    minimum: float
    maximum: float
    unit: str

    def decode(self, payload_int):
        mask = (1 << self.bit_length) - 1
        raw_value = (payload_int >> self.start_bit) & mask
        if self.is_signed and self.bit_length > 0:
            sign_bit = 1 << (self.bit_length - 1)
            if raw_value & sign_bit:
                raw_value -= 1 << self.bit_length
        physical_value = raw_value * self.factor + self.offset
        if isinstance(physical_value, float) and physical_value.is_integer():
            return int(physical_value)
        return physical_value


@dataclass
class MessageDefinition:
    raw_id: int
    frame_id: int
    name: str
    dlc: int
    signals: List[SignalDefinition] = field(default_factory=list)


class DbcRuntime:
    CLUSTER_TEMPLATE_ADDRESS = 0xA0

    def __init__(self, dbc_path):
        self.dbc_path = dbc_path
        self.messages_by_id = {}
        self.messages_in_order = []
        self.address_catalog = {}
        self._load()
        self._build_catalog()

    @staticmethod
    def normalize_frame_id(frame_id):
        return int(frame_id) & 0x1FFFFFFF

    @staticmethod
    def frame_address(frame_id):
        return f"{DbcRuntime.normalize_frame_id(frame_id) & 0xFF:02X}"

    @classmethod
    def _template_address(cls, address):
        normalized = str(address).upper()
        try:
            address_value = int(normalized, 16)
        except ValueError:
            return normalized
        if address_value == 0x00 or 0xA0 <= address_value <= 0xAF:
            return f"{cls.CLUSTER_TEMPLATE_ADDRESS:02X}"
        return normalized

    @classmethod
    def _template_frame_id(cls, frame_id):
        normalized_id = cls.normalize_frame_id(frame_id)
        address_value = normalized_id & 0xFF
        if address_value == 0x00 or 0xA0 <= address_value <= 0xAF:
            return (normalized_id & ~0xFF) | cls.CLUSTER_TEMPLATE_ADDRESS
        return normalized_id

    def _read_lines(self):
        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                with open(self.dbc_path, "r", encoding=encoding) as dbc_file:
                    return dbc_file.readlines()
            except UnicodeDecodeError:
                continue
        with open(self.dbc_path, "r", encoding="utf-8", errors="ignore") as dbc_file:
            return dbc_file.readlines()

    def _load(self):
        current_message = None
        for line in self._read_lines():
            message_match = MESSAGE_RE.match(line)
            if message_match:
                raw_id = int(message_match.group("raw_id"))
                current_message = MessageDefinition(
                    raw_id=raw_id,
                    frame_id=self.normalize_frame_id(raw_id),
                    name=message_match.group("name"),
                    dlc=int(message_match.group("dlc")),
                )
                self.messages_by_id[current_message.frame_id] = current_message
                self.messages_in_order.append(current_message)
                continue

            if current_message is None:
                continue

            signal_match = SIGNAL_RE.match(line)
            if not signal_match or signal_match.group("byte_order") != "1":
                continue

            current_message.signals.append(
                SignalDefinition(
                    name=signal_match.group("name"),
                    start_bit=int(signal_match.group("start")),
                    bit_length=int(signal_match.group("length")),
                    is_signed=signal_match.group("signed") == "-",
                    factor=float(signal_match.group("factor")),
                    offset=float(signal_match.group("offset")),
                    minimum=float(signal_match.group("minimum")),
                    maximum=float(signal_match.group("maximum")),
                    unit=signal_match.group("unit"),
                )
            )

    def _build_catalog(self):
        for message in self.messages_in_order:
            address = self.frame_address(message.frame_id)
            rows = self.address_catalog.setdefault(address, [])
            for signal in message.signals:
                rows.append(
                    {
                        "row_key": f"{message.name}.{signal.name}",
                        "message_name": message.name,
                        "signal_name": signal.name,
                        "unit": signal.unit,
                    }
                )

    def get_catalog(self, address):
        normalized_address = address.upper()
        catalog = self.address_catalog.get(normalized_address)
        if catalog is not None:
            return list(catalog)
        template_address = self._template_address(normalized_address)
        if template_address != normalized_address:
            return list(self.address_catalog.get(template_address, []))
        return []

    def resolve_message(self, frame_id):
        normalized_id = self.normalize_frame_id(frame_id)
        message = self.messages_by_id.get(normalized_id)
        if message is not None:
            return normalized_id, message
        template_id = self._template_frame_id(normalized_id)
        if template_id != normalized_id:
            message = self.messages_by_id.get(template_id)
            if message is not None:
                return normalized_id, message
        return normalized_id, None

    def decode_frame(self, frame_id, data):
        normalized_id, message = self.resolve_message(frame_id)
        if message is None:
            return None

        payload = bytes(data)
        payload_int = int.from_bytes(payload, byteorder="little", signed=False)
        available_bits = len(payload) * 8
        raw_address = self.frame_address(normalized_id)
        signals = []
        for signal in message.signals:
            if signal.start_bit + signal.bit_length > available_bits:
                continue
            signals.append(
                {
                    "row_key": f"{message.name}.{signal.name}",
                    "message_name": message.name,
                    "signal_name": signal.name,
                    "value": signal.decode(payload_int),
                    "unit": signal.unit,
                }
            )
        return {
            "frame_id": message.frame_id,
            "raw_frame_id": normalized_id,
            "message_name": message.name,
            "address": raw_address,
            "signals": signals,
        }
