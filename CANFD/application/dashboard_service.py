"""Application service for the all-cluster operations dashboard."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Tuple

from data_center.models import ActiveAlarm, DataQuality
from data_center.runtime_cache import RuntimeDataCenter
from protocol.bms_signal_ids import DASHBOARD_POLL_SEQUENCE


RUN_STATUS_TEXT = {
    0: "初始",
    1: "自检",
    2: "准备",
    3: "预充",
    4: "高压待机",
    5: "放电",
    6: "充电",
    7: "放空",
    8: "充满",
    9: "错误",
    10: "切断",
    11: "休眠",
}

DASHBOARD_VALUE_UNITS = {
    "soc": "%",
    "system_voltage": "V",
    "system_current": "A",
    "diff_voltage": "mV",
    "max_cell_voltage": "mV",
    "min_cell_voltage": "mV",
    "max_cell_temp": "℃",
    "diff_temp": "℃",
}

class ClusterHealth(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    ALARM = "alarm"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClusterDashboardView:
    cluster_index: int
    address: str
    communication_quality: DataQuality
    health: ClusterHealth
    run_status: Optional[int]
    run_status_text: str
    soc: Optional[float]
    system_voltage: Optional[float]
    system_current: Optional[float]
    voltage_difference: Optional[float]
    maximum_cell_voltage: Optional[float]
    minimum_cell_voltage: Optional[float]
    maximum_temperature: Optional[float]
    temperature_difference: Optional[float]
    alarm_count: int
    alarm_names: Tuple[str, ...]
    last_update: Optional[datetime]


@dataclass(frozen=True)
class FleetDashboardView:
    clusters: Tuple[ClusterDashboardView, ...]
    total_count: int
    online_count: int
    normal_count: int
    warning_count: int
    alarm_count: int
    offline_count: int
    generated_at: datetime


class DashboardService:
    """Builds dashboard view models from the unified runtime cache."""

    def __init__(
        self,
        protocol_service,
        data_center: RuntimeDataCenter,
        communication_timeout_s: float = 2.0,
    ):
        self.protocol_service = protocol_service
        self.data_center = data_center
        self.communication_timeout_s = max(float(communication_timeout_s), 0.1)
        self._query_cursor = 0

    def reset(self) -> None:
        self._query_cursor = 0
        self.data_center.clear_runtime_values()

    def reconfigure(self) -> None:
        self.data_center.configure_clusters(
            self.protocol_service.cluster_index_to_address
        )
        self.reset()

    def send_next_query(self) -> int:
        cluster_indices = tuple(self.protocol_service.cluster_indices)
        if not cluster_indices:
            return 0
        sequence_length = len(DASHBOARD_POLL_SEQUENCE)
        pair_index = self._query_cursor % (len(cluster_indices) * sequence_length)
        cluster_index = cluster_indices[pair_index // sequence_length]
        signal_id = DASHBOARD_POLL_SEQUENCE[pair_index % sequence_length]
        self._query_cursor = (pair_index + 1) % (
            len(cluster_indices) * sequence_length
        )
        return self.protocol_service.send_signal_query(cluster_index, int(signal_id))

    def ingest_poll_result(self, poll_result) -> None:
        affected_clusters = {
            int(update.cluster_index)
            for update in poll_result.legacy_updates
        }
        address_to_index = self.protocol_service.cluster_address_to_index
        for update in poll_result.periodic_updates:
            cluster_index = address_to_index.get(str(update.address).upper())
            if cluster_index is not None:
                affected_clusters.add(int(cluster_index))
        for cluster_index in affected_clusters:
            self.refresh_cluster(cluster_index)

    def refresh_all_clusters(self) -> None:
        for cluster_index in self.protocol_service.cluster_indices:
            self.refresh_cluster(cluster_index)

    def refresh_cluster(self, cluster_index: int) -> None:
        cluster_index = int(cluster_index)
        snapshot = self.protocol_service.get_index_monitor_snapshot(cluster_index)
        normalized_values = {
            "run_status": self._optional_int(snapshot.get("run_status")),
            "soc": self._scaled(snapshot.get("soc"), 10.0),
            "system_voltage": self._scaled(snapshot.get("system_voltage"), 10.0),
            "system_current": self._scaled(snapshot.get("system_current"), 10.0),
            "diff_voltage": self._scaled(snapshot.get("diff_voltage"), 1.0),
            "max_cell_voltage": self._scaled(
                snapshot.get("max_cell_voltage"),
                1.0,
            ),
            "min_cell_voltage": self._scaled(
                snapshot.get("min_cell_voltage"),
                1.0,
            ),
            "max_cell_temp": self._scaled(snapshot.get("max_cell_temp"), 10.0),
            "diff_temp": self._scaled(snapshot.get("diff_temp"), 10.0),
        }
        values = {
            key: value
            for key, value in normalized_values.items()
            if value is not None
        }
        activity = self.protocol_service.get_bus_activity_snapshot(cluster_index)
        quality, last_seen_at = self._communication_state(activity)
        if values:
            self.data_center.update_cluster_values(
                cluster_index,
                values,
                units=DASHBOARD_VALUE_UNITS,
                quality=quality,
                timestamp=last_seen_at or datetime.now(),
            )
        self.data_center.update_cluster_communication(
            cluster_index,
            quality,
            last_seen_at=last_seen_at,
        )
        address = self.protocol_service.cluster_index_to_address[cluster_index]
        self.data_center.replace_cluster_alarms(
            cluster_index,
            self._active_alarms(address),
        )

    def get_dashboard(self) -> FleetDashboardView:
        self._refresh_communication_quality()
        clusters = tuple(
            self._build_cluster_view(cluster)
            for cluster in self.data_center.list_clusters()
        )
        return FleetDashboardView(
            clusters=clusters,
            total_count=len(clusters),
            online_count=sum(
                cluster.communication_quality == DataQuality.GOOD
                for cluster in clusters
            ),
            normal_count=sum(cluster.health == ClusterHealth.NORMAL for cluster in clusters),
            warning_count=sum(cluster.health == ClusterHealth.WARNING for cluster in clusters),
            alarm_count=sum(cluster.alarm_count for cluster in clusters),
            offline_count=sum(cluster.health == ClusterHealth.OFFLINE for cluster in clusters),
            generated_at=datetime.now(),
        )

    def _refresh_communication_quality(self) -> None:
        now = datetime.now()
        for cluster_index in self.protocol_service.cluster_indices:
            activity = self.protocol_service.get_bus_activity_snapshot(cluster_index)
            quality, last_seen_at = self._communication_state(activity, now=now)
            self.data_center.update_cluster_communication(
                cluster_index,
                quality,
                last_seen_at=last_seen_at,
            )

    def _communication_state(self, activity, now=None):
        now = now or datetime.now()
        if not activity.get("is_open"):
            return DataQuality.OFFLINE, None
        last_rx_age_s = activity.get("last_rx_age_s")
        if last_rx_age_s is None:
            return DataQuality.UNKNOWN, None
        last_seen_at = now - timedelta(seconds=max(float(last_rx_age_s), 0.0))
        if float(last_rx_age_s) <= self.communication_timeout_s:
            return DataQuality.GOOD, last_seen_at
        return DataQuality.STALE, last_seen_at

    def _active_alarms(self, address):
        getter = getattr(
            self.protocol_service,
            "get_periodic_alarm_state_values",
            None,
        )
        if not callable(getter):
            return ()
        alarms = []
        for code, value in getter(address):
            try:
                level = int(float(value))
            except (TypeError, ValueError):
                level = 1 if value else 0
            if level <= 0:
                continue
            alarms.append(
                ActiveAlarm(
                    code=str(code),
                    name=str(code),
                    level=level,
                    timestamp=datetime.now(),
                )
            )
        return tuple(alarms)

    @staticmethod
    def _build_cluster_view(cluster):
        def value(key):
            latest_value = cluster.latest_values.get(key)
            return None if latest_value is None else latest_value.value

        alarm_names = tuple(alarm.name for alarm in cluster.active_alarms)
        voltage_difference = value("diff_voltage")
        maximum_temperature = value("max_cell_temp")
        temperature_difference = value("diff_temp")
        maximum_alarm_level = max(
            (alarm.level for alarm in cluster.active_alarms),
            default=0,
        )
        if cluster.communication_quality in (DataQuality.OFFLINE, DataQuality.STALE):
            health = ClusterHealth.OFFLINE
        elif maximum_alarm_level >= 2:
            health = ClusterHealth.ALARM
        elif cluster.active_alarms:
            health = ClusterHealth.WARNING
        elif cluster.communication_quality == DataQuality.UNKNOWN:
            health = ClusterHealth.UNKNOWN
        else:
            health = ClusterHealth.NORMAL
        run_status = value("run_status")
        return ClusterDashboardView(
            cluster_index=cluster.cluster_index,
            address=cluster.address,
            communication_quality=cluster.communication_quality,
            health=health,
            run_status=run_status,
            run_status_text=RUN_STATUS_TEXT.get(run_status, "--"),
            soc=value("soc"),
            system_voltage=value("system_voltage"),
            system_current=value("system_current"),
            voltage_difference=voltage_difference,
            maximum_cell_voltage=value("max_cell_voltage"),
            minimum_cell_voltage=value("min_cell_voltage"),
            maximum_temperature=maximum_temperature,
            temperature_difference=temperature_difference,
            alarm_count=len(alarm_names),
            alarm_names=alarm_names,
            last_update=cluster.last_seen_at,
        )

    @staticmethod
    def _scaled(value, divisor):
        if value is None:
            return None
        try:
            return float(value) / float(divisor)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _optional_int(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
