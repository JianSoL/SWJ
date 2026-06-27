import csv
import time
from datetime import datetime
from pathlib import Path


MAX_ROWS_PER_FILE = 100000
FLUSH_ROW_INTERVAL = 128
FLUSH_INTERVAL_S = 0.5


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _payload_hex(data):
    return " ".join(f"{int(byte):02X}" for byte in data)


def _format_snapshot_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _normalize_snapshot_values(values, expected_count):
    normalized = list(values[:expected_count])
    if len(normalized) < expected_count:
        normalized.extend([None] * (expected_count - len(normalized)))
    return normalized


def _safe_path_segment(value, fallback):
    text = str(value).strip() or str(fallback)
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "_" for char in text)


class _RollingCsvWriter:
    def __init__(
        self,
        path,
        header,
        max_rows,
        flush_row_interval=FLUSH_ROW_INTERVAL,
        flush_interval_s=FLUSH_INTERVAL_S,
    ):
        self.base_path = Path(path)
        self.header = list(header)
        self.max_rows = int(max_rows)
        self.part_index = 1
        self.row_count = 0
        self._file_handle = None
        self._writer = None
        self.flush_row_interval = max(1, int(flush_row_interval))
        self.flush_interval_s = max(0.0, float(flush_interval_s))
        self.pending_row_count = 0
        self.last_flush_monotonic = time.monotonic()
        self._initialize_file()

    @property
    def current_path(self):
        if self.part_index == 1:
            return self.base_path
        return self.base_path.with_name(
            f"{self.base_path.stem}_part{self.part_index}{self.base_path.suffix}"
        )

    def write_row(self, row):
        if self.row_count >= self.max_rows:
            self.part_index += 1
            self.row_count = 0
            self._initialize_file()

        self._writer.writerow(row)
        self.row_count += 1
        self.pending_row_count += 1
        now = time.monotonic()
        if (
            self.pending_row_count >= self.flush_row_interval
            or now - self.last_flush_monotonic >= self.flush_interval_s
        ):
            self.flush()

    def flush(self):
        if self._file_handle is None:
            return
        self._file_handle.flush()
        self.pending_row_count = 0
        self.last_flush_monotonic = time.monotonic()

    def close(self):
        if self._file_handle is not None:
            self.flush()
            self._file_handle.close()
            self._file_handle = None
            self._writer = None

    def _initialize_file(self):
        self.close()
        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle = open(self.current_path, "w", newline="", encoding="utf-8-sig")
        self._writer = csv.writer(self._file_handle)
        self._writer.writerow(self.header)
        self._file_handle.flush()
        self.pending_row_count = 0
        self.last_flush_monotonic = time.monotonic()


class SessionLogManager:
    def __init__(
        self,
        log_dir,
        cluster_indices,
        cluster_addresses,
        runtime_signal_names,
        voltage_count=0,
        temperature_count=0,
        balance_module_count=0,
        balance_cells_per_module=0,
        abnormal_count=0,
        enabled=True,
        max_rows_per_file=MAX_ROWS_PER_FILE,
    ):
        self.log_dir = Path(log_dir)
        self.cluster_indices = [int(index) for index in cluster_indices]
        self.cluster_addresses = [str(address).upper() for address in cluster_addresses]
        self.runtime_signal_names = list(runtime_signal_names)
        self.voltage_count = int(voltage_count)
        self.temperature_count = int(temperature_count)
        self.balance_module_count = int(balance_module_count)
        self.balance_cells_per_module = int(balance_cells_per_module)
        self.abnormal_count = int(abnormal_count)
        self.max_rows_per_file = int(max_rows_per_file)
        self.enabled = bool(enabled)

        self.cluster_address_by_index = {
            cluster_index: self.cluster_addresses[position]
            for position, cluster_index in enumerate(self.cluster_indices)
            if position < len(self.cluster_addresses)
        }
        self.cluster_index_by_address = {
            address: cluster_index
            for cluster_index, address in self.cluster_address_by_index.items()
        }

        self.tx_writer = None
        self.rx_writer = None
        self.runtime_writers = {}
        self.voltage_writers = {}
        self.temperature_writers = {}
        self.balance_writers = {}
        self.abnormal_writers = {}

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

    def log_tx(self, frame_kind, target_index, frame, result):
        if not self.enabled or self.tx_writer is None:
            return
        self.tx_writer.write_row(
            [
                _timestamp(),
                frame_kind,
                target_index,
                f"0x{int(frame.frame_id):08X}",
                1 if frame.extern_flag else 0,
                1 if frame.remote_flag else 0,
                frame.data_len,
                _payload_hex(frame.data),
                int(result),
            ]
        )

    def log_rx(self, frame_kind, frame, extra_fields=None):
        if not self.enabled or self.rx_writer is None:
            return
        self.rx_writer.write_row(
            [
                _timestamp(),
                frame_kind,
                f"0x{int(frame.frame_id):08X}",
                1 if frame.extern_flag else 0,
                1 if frame.remote_flag else 0,
                frame.data_len,
                _payload_hex(frame.data),
                ";".join(extra_fields or []),
            ]
        )

    def write_cluster_snapshot(self, cluster_index, signal_state):
        if not self.enabled:
            return
        writer = self.runtime_writers.get(int(cluster_index))
        if writer is None:
            return
        writer.write_row(
            [_timestamp()]
            + [_format_snapshot_value(signal_state.get(name, "")) for name in self.runtime_signal_names]
        )

    def write_voltage_snapshot(self, address, values):
        self._write_address_snapshot(
            self.voltage_writers,
            address,
            values,
            self.voltage_count,
        )

    def write_temperature_snapshot(self, address, values):
        self._write_address_snapshot(
            self.temperature_writers,
            address,
            values,
            self.temperature_count,
        )

    def write_balance_snapshot(self, address, values):
        self._write_address_snapshot(
            self.balance_writers,
            address,
            values,
            self.balance_module_count * self.balance_cells_per_module,
        )

    def write_abnormal_snapshot(self, address, values):
        self._write_address_snapshot(
            self.abnormal_writers,
            address,
            values,
            self.abnormal_count,
        )

    def close(self):
        for writer in self._all_writers():
            writer.close()

    def flush(self):
        for writer in self._all_writers():
            writer.flush()

    def _write_address_snapshot(self, writers, address, values, expected_count):
        if not self.enabled or expected_count <= 0:
            return
        writer = writers.get(str(address).upper())
        if writer is None:
            return
        writer.write_row(
            [_timestamp()]
            + [
                _format_snapshot_value(value)
                for value in _normalize_snapshot_values(values, expected_count)
            ]
        )

    def _prepare_session_paths(self):
        self.session_name = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
        self.tx_path = self.log_dir / f"{self.session_name}_can_tx.csv"
        self.rx_path = self.log_dir / f"{self.session_name}_can_rx.csv"
        self.cluster_dir_by_index = {
            cluster_index: self._cluster_dir_for_index(cluster_index)
            for cluster_index in self.cluster_indices
        }
        self.cluster_dir_by_address = {
            address: self._cluster_dir_for_address(address)
            for address in self.cluster_addresses
        }
        self.runtime_path_by_index = {
            cluster_index: (
                self.cluster_dir_by_index[cluster_index]
                / "runtime"
                / f"{self.session_name}_runtime_cluster_{cluster_index}.csv"
            )
            for cluster_index in self.cluster_indices
        }
        self.voltage_path_by_address = self._address_paths("voltage")
        self.temperature_path_by_address = self._address_paths("temperature")
        self.balance_path_by_address = self._address_paths("balance")
        self.abnormal_path_by_address = self._address_paths("abnormal")

    def _start_session(self):
        self._prepare_session_paths()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_files()

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
        runtime_header = ["timestamp"] + self.runtime_signal_names
        self.runtime_writers = {
            cluster_index: _RollingCsvWriter(path, runtime_header, self.max_rows_per_file)
            for cluster_index, path in self.runtime_path_by_index.items()
        }
        self.voltage_writers = self._build_address_writers(
            self.voltage_path_by_address,
            self._numbered_header("CELL", self.voltage_count),
        )
        self.temperature_writers = self._build_address_writers(
            self.temperature_path_by_address,
            self._numbered_header("TEMP", self.temperature_count),
        )
        balance_count = self.balance_module_count * self.balance_cells_per_module
        balance_header = []
        if balance_count > 0:
            balance_header = ["timestamp"] + [
                f"M{module_index + 1}-{cell_index + 1:03d}"
                for module_index in range(self.balance_module_count)
                for cell_index in range(self.balance_cells_per_module)
            ]
        self.balance_writers = self._build_address_writers(
            self.balance_path_by_address,
            balance_header,
        )
        self.abnormal_writers = self._build_address_writers(
            self.abnormal_path_by_address,
            self._numbered_header("ABNORMAL", self.abnormal_count),
        )

    def _build_address_writers(self, paths, header):
        if not header:
            return {}
        return {
            address: _RollingCsvWriter(path, header, self.max_rows_per_file)
            for address, path in paths.items()
        }

    def _numbered_header(self, prefix, count):
        if count <= 0:
            return []
        return ["timestamp"] + [f"{prefix}_{index:03d}" for index in range(1, count + 1)]

    def _address_paths(self, category):
        return {
            address: (
                self.cluster_dir_by_address[address]
                / category
                / f"{self.session_name}_{category}_{address}.csv"
            )
            for address in self.cluster_addresses
        }

    def _cluster_dir_for_index(self, cluster_index):
        address = self.cluster_address_by_index.get(cluster_index)
        cluster_segment = _safe_path_segment(cluster_index, "unknown")
        if address is None:
            return self.log_dir / f"cluster_{cluster_segment}"
        return self.log_dir / f"cluster_{cluster_segment}_{_safe_path_segment(address, 'unknown')}"

    def _cluster_dir_for_address(self, address):
        cluster_index = self.cluster_index_by_address.get(str(address).upper())
        if cluster_index is not None:
            return self.cluster_dir_by_index[cluster_index]
        return self.log_dir / f"cluster_address_{_safe_path_segment(address, 'unknown')}"

    def _all_writers(self):
        writers = [self.tx_writer, self.rx_writer]
        writers.extend(self.runtime_writers.values())
        writers.extend(self.voltage_writers.values())
        writers.extend(self.temperature_writers.values())
        writers.extend(self.balance_writers.values())
        writers.extend(self.abnormal_writers.values())
        return [writer for writer in writers if writer is not None]
