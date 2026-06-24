import re
from dataclasses import dataclass, field
from pathlib import Path


MESSAGE_RE = re.compile(r"^BO_\s+(\d+)\s+(\S+)\s*:\s*(\d+)\s+(.+?)\s*$")
SIGNAL_RE = re.compile(
    r"^\s*SG_\s+(\S+)(?:\s+([mM]\d*|M))?\s*:\s*"
    r"(\d+)\|(\d+)@([01])([+-])\s*"
    r"\(([-+0-9.eE]+),([-+0-9.eE]+)\)\s*"
    r"\[([-+0-9.eE]+)\|([-+0-9.eE]+)\]\s*"
    r'"([^"]*)"\s*(.*?)\s*$'
)
NODE_RE = re.compile(r"^BU_:\s*(.*?)\s*$")
COMMENT_MESSAGE_RE = re.compile(r'^CM_\s+BO_\s+(\d+)\s+"(.*)"\s*;\s*$', re.DOTALL)
COMMENT_SIGNAL_RE = re.compile(r'^CM_\s+SG_\s+(\d+)\s+(\S+)\s+"(.*)"\s*;\s*$', re.DOTALL)
VALUE_RE = re.compile(r"^VAL_\s+(\d+)\s+(\S+)\s+(.*?)\s*;\s*$")
VALUE_CHOICE_RE = re.compile(r'(-?\d+)\s+"([^"]*)"')


@dataclass
class DbcSignal:
    name: str
    start_bit: int
    length: int
    byte_order: str
    is_signed: bool
    factor: float
    offset: float
    minimum: float
    maximum: float
    unit: str
    receivers: str
    multiplexer: str = ""
    comment: str = ""
    choices: dict = field(default_factory=dict)


@dataclass
class DbcMessage:
    frame_id: int
    name: str
    dlc: int
    transmitter: str
    comment: str = ""
    signals: list = field(default_factory=list)

    @property
    def frame_id_hex(self):
        return f"0x{self.frame_id:X}"


@dataclass
class DbcDatabase:
    path: str
    encoding: str
    nodes: list
    messages: list
    parse_warnings: list = field(default_factory=list)

    @property
    def signal_count(self):
        return sum(len(message.signals) for message in self.messages)


def parse_number(text):
    value = float(str(text).strip())
    return int(value) if value.is_integer() else value


def _read_dbc_text(path):
    dbc_path = Path(path)
    last_error = None
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            return dbc_path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    return dbc_path.read_text(encoding="utf-8", errors="replace"), f"utf-8-replace ({last_error})"


def _parse_choices(raw_choices):
    choices = {}
    for raw_value, label in VALUE_CHOICE_RE.findall(raw_choices or ""):
        choices[int(raw_value)] = label
    return choices


def _iter_logical_lines(text):
    buffer = []
    start_line = 1
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if buffer:
            buffer.append(stripped)
            if re.search(r'"\s*;\s*$', stripped):
                yield start_line, "\n".join(buffer)
                buffer = []
            continue
        if re.match(r"^CM_\s+", stripped) and not re.search(r'"\s*;\s*$', stripped):
            buffer = [stripped]
            start_line = line_number
            continue
        yield line_number, raw_line
    if buffer:
        yield start_line, "\n".join(buffer)


def parse_dbc_file(path):
    dbc_path = Path(path)
    if not dbc_path.exists():
        raise FileNotFoundError(f"DBC文件不存在: {dbc_path}")

    text, encoding = _read_dbc_text(dbc_path)
    messages = []
    message_by_id = {}
    nodes = []
    pending_message_comments = {}
    pending_signal_comments = {}
    pending_choices = {}
    current_message = None
    warnings = []

    for line_number, raw_line in _iter_logical_lines(text):
        line = raw_line.strip()
        if not line:
            continue

        node_match = NODE_RE.match(line)
        if node_match:
            nodes = [node for node in node_match.group(1).split() if node]
            continue

        message_match = MESSAGE_RE.match(line)
        if message_match:
            frame_id = int(message_match.group(1))
            current_message = DbcMessage(
                frame_id=frame_id,
                name=message_match.group(2),
                dlc=int(message_match.group(3)),
                transmitter=message_match.group(4).strip(),
                comment=pending_message_comments.pop(frame_id, ""),
            )
            messages.append(current_message)
            message_by_id[frame_id] = current_message
            continue

        signal_match = SIGNAL_RE.match(line)
        if signal_match and current_message is not None:
            frame_comments = pending_signal_comments.get(current_message.frame_id, {})
            frame_choices = pending_choices.get(current_message.frame_id, {})
            signal = DbcSignal(
                name=signal_match.group(1),
                multiplexer=signal_match.group(2) or "",
                start_bit=int(signal_match.group(3)),
                length=int(signal_match.group(4)),
                byte_order="Intel" if signal_match.group(5) == "1" else "Motorola",
                is_signed=signal_match.group(6) == "-",
                factor=parse_number(signal_match.group(7)),
                offset=parse_number(signal_match.group(8)),
                minimum=parse_number(signal_match.group(9)),
                maximum=parse_number(signal_match.group(10)),
                unit=signal_match.group(11),
                receivers=signal_match.group(12).strip(),
                comment=frame_comments.get(signal_match.group(1), ""),
                choices=frame_choices.get(signal_match.group(1), {}),
            )
            current_message.signals.append(signal)
            continue

        message_comment_match = COMMENT_MESSAGE_RE.match(line)
        if message_comment_match:
            frame_id = int(message_comment_match.group(1))
            comment = message_comment_match.group(2).strip()
            if frame_id in message_by_id:
                message_by_id[frame_id].comment = comment
            else:
                pending_message_comments[frame_id] = comment
            continue

        signal_comment_match = COMMENT_SIGNAL_RE.match(line)
        if signal_comment_match:
            frame_id = int(signal_comment_match.group(1))
            signal_name = signal_comment_match.group(2)
            comment = signal_comment_match.group(3).strip()
            message = message_by_id.get(frame_id)
            if message is not None:
                applied = False
                for signal in message.signals:
                    if signal.name == signal_name:
                        signal.comment = comment
                        applied = True
                        break
                if not applied:
                    pending_signal_comments.setdefault(frame_id, {})[signal_name] = comment
            else:
                pending_signal_comments.setdefault(frame_id, {})[signal_name] = comment
            continue

        value_match = VALUE_RE.match(line)
        if value_match:
            frame_id = int(value_match.group(1))
            signal_name = value_match.group(2)
            choices = _parse_choices(value_match.group(3))
            message = message_by_id.get(frame_id)
            if message is not None:
                applied = False
                for signal in message.signals:
                    if signal.name == signal_name:
                        signal.choices = choices
                        applied = True
                        break
                if not applied:
                    pending_choices.setdefault(frame_id, {})[signal_name] = choices
            else:
                pending_choices.setdefault(frame_id, {})[signal_name] = choices
            continue

        if line.startswith(("BO_ ", "SG_ ", "CM_ ", "VAL_ ")):
            warnings.append(f"第{line_number}行未解析: {line[:120]}")

    return DbcDatabase(
        path=str(dbc_path),
        encoding=encoding,
        nodes=nodes,
        messages=messages,
        parse_warnings=warnings,
    )
