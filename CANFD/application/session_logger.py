import csv
import json
from datetime import datetime
from pathlib import Path


MAX_ROWS_PER_FILE = 100000


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _payload_hex(data):
    return " ".join(f"{byte:02X}" for byte in data)


def _format_snapshot_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _normalize_snapshot_values(values, expected_count):
    normalized_values = list(values[:expected_count])
    if len(normalized_values) < expected_count:
        normalized_values.extend([None] * (expected_count - len(normalized_values)))
    return normalized_values


class _RollingCsvWriter:
    def __init__(self, path, header, max_rows):
        self.base_path = Path(path)
        self.header = list(header)
        self.max_rows = max_rows
        self.part_index = 1
        self.row_count = 0
        self._file_handle = None
        self._writer = None
        self._initialize_file()

    def write_row(self, row):
        if self.row_count >= self.max_rows:
            self.part_index += 1
            self.row_count = 0
            self._initialize_file()

        self._writer.writerow(row)
        self._file_handle.flush()
        self.row_count += 1

    def close(self):
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
            self._writer = None

    @property
    def current_path(self):
        if self.part_index == 1:
            return self.base_path
        return self.base_path.with_name(
            f"{self.base_path.stem}_part{self.part_index}{self.base_path.suffix}"
        )

    def _initialize_file(self):
        self.close()
        self._file_handle = open(self.current_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file_handle)
        self._writer.writerow(self.header)
        self._file_handle.flush()


class SessionLogManager:
    def __init__(
        self,
        log_dir,
        cluster_count=None,
        legacy_signal_names=(),
        max_rows_per_file=MAX_ROWS_PER_FILE,
        cluster_indices=None,
        cluster_addresses=None,
        voltage_count=0,
        temperature_count=0,
        balance_module_count=0,
        balance_cells_per_module=0,
        enabled=True,
        console_echo=False,
    ):
        self.enabled = bool(enabled)
        self.console_echo = bool(console_echo)
        self.log_dir = Path(log_dir)
        self.max_rows_per_file = max_rows_per_file
        if cluster_indices is None:
            if cluster_count is None:
                raise ValueError("cluster_count or cluster_indices is required")
            self.cluster_indices = list(range(1, cluster_count + 1))
        else:
            self.cluster_indices = list(cluster_indices)
        self.cluster_addresses = [str(address) for address in (cluster_addresses or [])]
        self.legacy_signal_names = list(legacy_signal_names)
        self.voltage_count = int(voltage_count)
        self.temperature_count = int(temperature_count)
        self.balance_module_count = int(balance_module_count)
        self.balance_cells_per_module = int(balance_cells_per_module)
        self.tx_writer = None
        self.rx_writer = None
        self.dbc_writer = None
        self.cluster_writers = {}
        self.voltage_writers = {}
        self.temperature_writers = {}
        self.balance_writers = {}

        self._prepare_session_paths()
        if self.enabled:
            self._start_session()

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return

        if not enabled:
            self.enabled = False
            self.close()
            return

        self.enabled = True
        self._start_session()

    def _initialize_files(self):
        self.tx_writer = _RollingCsvWriter(
            self.tx_path,
            [
                "timestamp",
                "frame_kind",
                "target_index",
                "can_id",
                "extern_flag",
                "remote_flag",
                "data_len",
                "data_hex",
                "tx_result",
            ],
            self.max_rows_per_file,
        )

        self.rx_writer = _RollingCsvWriter(
            self.rx_path,
            [
                "timestamp",
                "frame_kind",
                "can_id",
                "extern_flag",
                "remote_flag",
                "data_len",
                "data_hex",
                "extra",
            ],
            self.max_rows_per_file,
        )

        self.dbc_writer = _RollingCsvWriter(
            self.dbc_path,
            [
                "timestamp",
                "frame_kind",
                "raw_can_id",
                "dbc_can_id",
                "address",
                "message_name",
                "signal_count",
                "signals_json",
            ],
            self.max_rows_per_file,
        )

        header = ["timestamp"] + self.legacy_signal_names
        self.cluster_writers = {
            cluster_index: _RollingCsvWriter(cluster_path, header, self.max_rows_per_file)
            for cluster_index, cluster_path in self.cluster_path_by_index.items()
        }

        if self.cluster_addresses and self.voltage_count > 0:
            voltage_header = ["timestamp"] + [
                f"CELL_{index:03d}"
                for index in range(1, self.voltage_count + 1)
            ]
            self.voltage_writers = {
                address: _RollingCsvWriter(path, voltage_header, self.max_rows_per_file)
                for address, path in self.voltage_path_by_address.items()
            }
        else:
            self.voltage_writers = {}

        if self.cluster_addresses and self.temperature_count > 0:
            temperature_header = ["timestamp"] + [
                f"TEMP_{index:03d}"
                for index in range(1, self.temperature_count + 1)
            ]
            self.temperature_writers = {
                address: _RollingCsvWriter(path, temperature_header, self.max_rows_per_file)
                for address, path in self.temperature_path_by_address.items()
            }
        else:
            self.temperature_writers = {}

        if (
            self.cluster_addresses
            and self.balance_module_count > 0
            and self.balance_cells_per_module > 0
        ):
            balance_header = ["timestamp"] + [
                f"M{module_index + 1}-{cell_index + 1:03d}"
                for module_index in range(self.balance_module_count)
                for cell_index in range(self.balance_cells_per_module)
            ]
            self.balance_writers = {
                address: _RollingCsvWriter(path, balance_header, self.max_rows_per_file)
                for address, path in self.balance_path_by_address.items()
            }
        else:
            self.balance_writers = {}

    def _prepare_session_paths(self):
        self.session_name = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
        self.tx_path = self.log_dir / f"{self.session_name}_can_tx.csv"
        self.rx_path = self.log_dir / f"{self.session_name}_can_rx.csv"
        self.dbc_path = self.log_dir / f"{self.session_name}_dbc.csv"
        self.cluster_paths = [
            self.log_dir / f"{self.session_name}_cluster_{cluster_index}.csv"
            for cluster_index in self.cluster_indices
        ]
        self.cluster_path_by_index = dict(zip(self.cluster_indices, self.cluster_paths))
        self.voltage_path_by_address = {
            address: self.log_dir / f"{self.session_name}_voltage_{address}.csv"
            for address in self.cluster_addresses
        }
        self.temperature_path_by_address = {
            address: self.log_dir / f"{self.session_name}_temperature_{address}.csv"
            for address in self.cluster_addresses
        }
        self.balance_path_by_address = {
            address: self.log_dir / f"{self.session_name}_balance_{address}.csv"
            for address in self.cluster_addresses
        }

    def _start_session(self):
        self._prepare_session_paths()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_files()

    def log_tx(self, frame_kind, target_index, frame, result):
        if not self.enabled:
            return
        row = [
            _timestamp(),
            frame_kind,
            target_index,
            f"0x{frame.frame_id:08X}",
            1 if frame.extern_flag else 0,
            1 if frame.remote_flag else 0,
            frame.data_len,
            _payload_hex(frame.data),
            result,
        ]
        if self.console_echo:
            print(",".join(str(item) for item in row), flush=True)
        self.tx_writer.write_row(row)

    def log_rx(self, frame_kind, frame, extra_fields=None):
        if not self.enabled:
            return
        extra_text = ";".join(extra_fields or [])
        row = [
            _timestamp(),
            frame_kind,
            f"0x{frame.frame_id:08X}",
            1 if frame.extern_flag else 0,
            1 if frame.remote_flag else 0,
            frame.data_len,
            _payload_hex(frame.data),
            extra_text,
        ]
        if self.console_echo:
            line = ",".join(str(item) for item in row)
            print(line, flush=True)
            if (frame.frame_id & 0xFFFFFF00) == 0x1881F200:
                print(f"RX_REPLY_HIT,{line}", flush=True)
        self.rx_writer.write_row(row)

    def log_dbc(self, frame_kind, frame, decoded):
        if not self.enabled:
            return
        signals_json = json.dumps(
            [
                {
                    "signal_name": signal["signal_name"],
                    "value": signal["value"],
                    "unit": signal["unit"],
                }
                for signal in decoded["signals"]
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        row = [
            _timestamp(),
            frame_kind,
            f"0x{frame.frame_id:08X}",
            f"0x{decoded['frame_id']:08X}",
            decoded["address"],
            decoded["message_name"],
            len(decoded["signals"]),
            signals_json,
        ]
        self.dbc_writer.write_row(row)

    def write_cluster_snapshot(self, cluster_index, signal_state):
        if not self.enabled:
            return
        row = [_timestamp()] + [signal_state.get(name, "") for name in self.legacy_signal_names]
        self.cluster_writers[cluster_index].write_row(row)

    def write_voltage_snapshot(self, address, values):
        if not self.enabled or address not in self.voltage_writers:
            return
        row = [_timestamp()] + [
            _format_snapshot_value(value)
            for value in _normalize_snapshot_values(values, self.voltage_count)
        ]
        self.voltage_writers[address].write_row(row)

    def write_temperature_snapshot(self, address, values):
        if not self.enabled or address not in self.temperature_writers:
            return
        row = [_timestamp()] + [
            _format_snapshot_value(value)
            for value in _normalize_snapshot_values(values, self.temperature_count)
        ]
        self.temperature_writers[address].write_row(row)

    def write_balance_snapshot(self, address, values):
        if not self.enabled or address not in self.balance_writers:
            return
        row = [_timestamp()] + [
            _format_snapshot_value(value)
            for value in _normalize_snapshot_values(
                values,
                self.balance_module_count * self.balance_cells_per_module,
            )
        ]
        self.balance_writers[address].write_row(row)

    def close(self):
        if self.tx_writer is not None:
            self.tx_writer.close()
        if self.rx_writer is not None:
            self.rx_writer.close()
        if self.dbc_writer is not None:
            self.dbc_writer.close()
        for writer in self.cluster_writers.values():
            writer.close()
        for writer in self.voltage_writers.values():
            writer.close()
        for writer in self.temperature_writers.values():
            writer.close()
        for writer in self.balance_writers.values():
            writer.close()
