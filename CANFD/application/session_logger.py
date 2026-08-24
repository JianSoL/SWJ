import csv
import json
import time
from datetime import datetime
from pathlib import Path


MAX_ROWS_PER_FILE = 100000
DEFAULT_FLUSH_INTERVAL_MS = 250
DEFAULT_FLUSH_ROW_COUNT = 128


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _payload_hex(data):
    return bytes(data).hex(" ").upper()


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


def _safe_path_segment(value, fallback):
    text = str(value).strip()
    if not text:
        text = str(fallback)
    return "".join(
        char if char.isalnum() or char in ("-", "_", ".") else "_"
        for char in text
    )


class _RollingCsvWriter:
    def __init__(
        self,
        path,
        header,
        max_rows,
        flush_interval_ms=DEFAULT_FLUSH_INTERVAL_MS,
        flush_row_count=DEFAULT_FLUSH_ROW_COUNT,
    ):
        self.base_path = Path(path)
        self.header = list(header)
        self.max_rows = max_rows
        self.flush_interval_s = max(int(flush_interval_ms), 1) / 1000.0
        self.flush_row_count = max(int(flush_row_count), 1)
        self.part_index = 1
        self.row_count = 0
        self._pending_flush_rows = 0
        self._last_flush_at = time.monotonic()
        self._file_handle = None
        self._writer = None
        self._initialize_file()

    def write_row(self, row):
        if self.row_count >= self.max_rows:
            self.part_index += 1
            self.row_count = 0
            self._initialize_file()

        self._writer.writerow(row)
        self.row_count += 1
        self._pending_flush_rows += 1
        if (
            self._pending_flush_rows >= self.flush_row_count
            or time.monotonic() - self._last_flush_at >= self.flush_interval_s
        ):
            self.flush()

    def flush(self):
        if self._file_handle is None or self._pending_flush_rows <= 0:
            return
        self._file_handle.flush()
        self._pending_flush_rows = 0
        self._last_flush_at = time.monotonic()

    def close(self):
        if self._file_handle is not None:
            self.flush()
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
        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle = open(
            self.current_path,
            "w",
            newline="",
            encoding="utf-8",
            buffering=1024 * 1024,
        )
        self._writer = csv.writer(self._file_handle)
        self._writer.writerow(self.header)
        self._file_handle.flush()
        self._pending_flush_rows = 0
        self._last_flush_at = time.monotonic()


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
        balance_temperature_per_module=0,
        enabled=True,
        console_echo=False,
        flush_interval_ms=DEFAULT_FLUSH_INTERVAL_MS,
        flush_row_count=DEFAULT_FLUSH_ROW_COUNT,
    ):
        self.enabled = bool(enabled)
        self.console_echo = bool(console_echo)
        self.log_dir = Path(log_dir)
        self.max_rows_per_file = max_rows_per_file
        self.flush_interval_ms = max(int(flush_interval_ms), 1)
        self.flush_row_count = max(int(flush_row_count), 1)
        if cluster_indices is None:
            if cluster_count is None:
                raise ValueError("cluster_count or cluster_indices is required")
            self.cluster_indices = list(range(1, cluster_count + 1))
        else:
            self.cluster_indices = list(cluster_indices)
        self.cluster_addresses = [str(address) for address in (cluster_addresses or [])]
        self.cluster_address_by_index = {
            cluster_index: self.cluster_addresses[position]
            for position, cluster_index in enumerate(self.cluster_indices)
            if position < len(self.cluster_addresses)
        }
        self.cluster_index_by_address = {
            address: cluster_index
            for cluster_index, address in self.cluster_address_by_index.items()
        }
        self.legacy_signal_names = self._normalize_signal_names(
            legacy_signal_names
        )
        self.voltage_count = int(voltage_count)
        self.temperature_count = int(temperature_count)
        self.balance_module_count = int(balance_module_count)
        self.balance_cells_per_module = int(balance_cells_per_module)
        self.balance_temperature_per_module = int(balance_temperature_per_module)
        self.tx_writer = None
        self.rx_writer = None
        self.dbc_writer = None
        self.cluster_writers = {}
        self.voltage_writers = {}
        self.temperature_writers = {}
        self.balance_temperature_writers = {}
        self.balance_writers = {}

        self._prepare_session_paths()
        if self.enabled:
            self._start_session()

    def update_layout(
        self,
        cluster_indices,
        cluster_addresses,
        legacy_signal_names=None,
        voltage_count=0,
        temperature_count=0,
        balance_module_count=0,
        balance_cells_per_module=0,
        balance_temperature_per_module=0,
    ):
        was_enabled = self.enabled
        self.close()
        self.cluster_indices = list(cluster_indices)
        self.cluster_addresses = [str(address) for address in cluster_addresses]
        self.cluster_address_by_index = {
            cluster_index: self.cluster_addresses[position]
            for position, cluster_index in enumerate(self.cluster_indices)
            if position < len(self.cluster_addresses)
        }
        self.cluster_index_by_address = {
            address: cluster_index
            for cluster_index, address in self.cluster_address_by_index.items()
        }
        if legacy_signal_names is not None:
            self.legacy_signal_names = self._normalize_signal_names(
                legacy_signal_names
            )
        self.voltage_count = int(voltage_count)
        self.temperature_count = int(temperature_count)
        self.balance_module_count = int(balance_module_count)
        self.balance_cells_per_module = int(balance_cells_per_module)
        self.balance_temperature_per_module = int(balance_temperature_per_module)
        if was_enabled:
            self._start_session()

    @staticmethod
    def _normalize_signal_names(signal_names):
        return list(dict.fromkeys(str(name) for name in (signal_names or ())))

    def update_legacy_signal_names(self, legacy_signal_names):
        signal_names = self._normalize_signal_names(legacy_signal_names)
        if signal_names == self.legacy_signal_names:
            return False

        for writer in self.cluster_writers.values():
            writer.close()
        self.cluster_writers = {}
        self.legacy_signal_names = signal_names
        self._prepare_cluster_snapshot_paths(
            datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
        )
        if self.enabled:
            header = ["timestamp"] + self.legacy_signal_names
            self.cluster_writers = {
                cluster_index: self._create_writer(cluster_path, header)
                for cluster_index, cluster_path in self.cluster_path_by_index.items()
            }
        return True

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
        self.tx_writer = self._create_writer(
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
        )

        self.rx_writer = self._create_writer(
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
        )

        self.dbc_writer = self._create_writer(
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
        )

        header = ["timestamp"] + self.legacy_signal_names
        self.cluster_writers = {
            cluster_index: self._create_writer(cluster_path, header)
            for cluster_index, cluster_path in self.cluster_path_by_index.items()
        }

        if self.cluster_addresses and self.voltage_count > 0:
            voltage_header = ["timestamp"] + [
                f"CELL_{index:03d}"
                for index in range(1, self.voltage_count + 1)
            ]
            self.voltage_writers = {
                address: self._create_writer(path, voltage_header)
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
                address: self._create_writer(path, temperature_header)
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
                address: self._create_writer(path, balance_header)
                for address, path in self.balance_path_by_address.items()
            }
        else:
            self.balance_writers = {}

        if (
            self.cluster_addresses
            and self.balance_module_count > 0
            and self.balance_temperature_per_module > 0
        ):
            balance_temperature_header = ["timestamp"] + [
                f"M{module_index + 1}-BT{temperature_index + 1:03d}"
                for module_index in range(self.balance_module_count)
                for temperature_index in range(self.balance_temperature_per_module)
            ]
            self.balance_temperature_writers = {
                address: self._create_writer(
                    path,
                    balance_temperature_header,
                )
                for address, path in self.balance_temperature_path_by_address.items()
            }
        else:
            self.balance_temperature_writers = {}

    def _create_writer(self, path, header):
        return _RollingCsvWriter(
            path,
            header,
            self.max_rows_per_file,
            flush_interval_ms=self.flush_interval_ms,
            flush_row_count=self.flush_row_count,
        )

    def _prepare_session_paths(self):
        self.session_name = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
        self.tx_path = self.log_dir / f"{self.session_name}_can_tx.csv"
        self.rx_path = self.log_dir / f"{self.session_name}_can_rx.csv"
        self.dbc_path = self.log_dir / f"{self.session_name}_dbc.csv"
        self.cluster_dir_by_index = {
            cluster_index: self._cluster_dir_for_index(cluster_index)
            for cluster_index in self.cluster_indices
        }
        self.cluster_dir_by_address = {
            address: self._cluster_dir_for_address(address)
            for address in self.cluster_addresses
        }
        self._prepare_cluster_snapshot_paths(self.session_name)
        self.voltage_path_by_address = {
            address: (
                self.cluster_dir_by_address[address]
                / "voltage"
                / f"{self.session_name}_voltage_{address}.csv"
            )
            for address in self.cluster_addresses
        }
        self.temperature_path_by_address = {
            address: (
                self.cluster_dir_by_address[address]
                / "temperature"
                / f"{self.session_name}_temperature_{address}.csv"
            )
            for address in self.cluster_addresses
        }
        self.balance_path_by_address = {
            address: (
                self.cluster_dir_by_address[address]
                / "balance"
                / f"{self.session_name}_balance_{address}.csv"
            )
            for address in self.cluster_addresses
        }
        self.balance_temperature_path_by_address = {
            address: (
                self.cluster_dir_by_address[address]
                / "balance_temperature"
                / f"{self.session_name}_balance_temperature_{address}.csv"
            )
            for address in self.cluster_addresses
        }

    def _prepare_cluster_snapshot_paths(self, session_name):
        self.cluster_paths = [
            self.cluster_dir_by_index[cluster_index]
            / "legacy"
            / f"{session_name}_cluster_{cluster_index}.csv"
            for cluster_index in self.cluster_indices
        ]
        self.cluster_path_by_index = dict(zip(self.cluster_indices, self.cluster_paths))

    def _cluster_dir_for_index(self, cluster_index):
        address = self.cluster_address_by_index.get(cluster_index)
        cluster_segment = _safe_path_segment(cluster_index, "unknown")
        if address is None:
            return self.log_dir / f"cluster_{cluster_segment}"
        address_segment = _safe_path_segment(address, "unknown")
        return self.log_dir / f"cluster_{cluster_segment}_{address_segment}"

    def _cluster_dir_for_address(self, address):
        cluster_index = self.cluster_index_by_address.get(str(address))
        if cluster_index is not None:
            return self.cluster_dir_by_index[cluster_index]
        address_segment = _safe_path_segment(address, "unknown")
        return self.log_dir / f"cluster_address_{address_segment}"

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

    def write_balance_temperature_snapshot(self, address, values):
        if not self.enabled or address not in self.balance_temperature_writers:
            return
        row = [_timestamp()] + [
            _format_snapshot_value(value)
            for value in _normalize_snapshot_values(
                values,
                self.balance_module_count * self.balance_temperature_per_module,
            )
        ]
        self.balance_temperature_writers[address].write_row(row)

    def flush(self):
        writers = [self.tx_writer, self.rx_writer, self.dbc_writer]
        writers.extend(self.cluster_writers.values())
        writers.extend(self.voltage_writers.values())
        writers.extend(self.temperature_writers.values())
        writers.extend(self.balance_temperature_writers.values())
        writers.extend(self.balance_writers.values())
        for writer in writers:
            if writer is not None:
                writer.flush()

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
        for writer in self.balance_temperature_writers.values():
            writer.close()
        for writer in self.balance_writers.values():
            writer.close()
        self.tx_writer = None
        self.rx_writer = None
        self.dbc_writer = None
        self.cluster_writers = {}
        self.voltage_writers = {}
        self.temperature_writers = {}
        self.balance_temperature_writers = {}
        self.balance_writers = {}
