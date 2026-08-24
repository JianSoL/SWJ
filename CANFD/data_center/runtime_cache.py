"""Thread-safe unified runtime cache used by application services."""

from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Dict, Iterable, Mapping, Optional, Sequence

from data_center.models import (
    ActiveAlarm,
    ClusterNode,
    DataQuality,
    LatestValue,
    SignalStatistics,
    StackNode,
    SystemNode,
)


DEFAULT_SYSTEM_ID = "bms_system"
DEFAULT_STACK_ID = "stack_1"


class RuntimeDataCenter:
    """Owns the latest value, quality, timestamp, alarm and statistics state."""

    def __init__(self, cluster_addresses: Mapping[int, str]):
        self._lock = RLock()
        self._system = SystemNode(
            system_id=DEFAULT_SYSTEM_ID,
            stacks={DEFAULT_STACK_ID: StackNode(stack_id=DEFAULT_STACK_ID)},
        )
        self.configure_clusters(cluster_addresses)

    def configure_clusters(self, cluster_addresses: Mapping[int, str]) -> None:
        normalized = {
            int(cluster_index): str(address).upper()
            for cluster_index, address in cluster_addresses.items()
        }
        with self._lock:
            stack = self._system.stacks[DEFAULT_STACK_ID]
            previous = stack.clusters
            stack.clusters = {
                cluster_index: self._reuse_or_create_cluster(
                    previous.get(cluster_index),
                    cluster_index,
                    address,
                )
                for cluster_index, address in normalized.items()
            }

    @staticmethod
    def _reuse_or_create_cluster(previous, cluster_index, address):
        if previous is not None and previous.address == address:
            return previous
        return ClusterNode(cluster_index=cluster_index, address=address)

    def update_cluster_values(
        self,
        cluster_index: int,
        values: Mapping[str, object],
        units: Optional[Mapping[str, str]] = None,
        quality: DataQuality = DataQuality.GOOD,
        timestamp: Optional[datetime] = None,
    ) -> None:
        timestamp = timestamp or datetime.now()
        units = units or {}
        with self._lock:
            cluster = self._cluster(cluster_index)
            for key, value in values.items():
                if value is None:
                    continue
                previous = cluster.latest_values.get(str(key))
                statistics = self._next_statistics(previous, value)
                cluster.latest_values[str(key)] = LatestValue(
                    value=value,
                    unit=str(units.get(key, "")),
                    quality=quality,
                    timestamp=timestamp,
                    statistics=statistics,
                )
            if values:
                cluster.last_seen_at = timestamp

    def update_cluster_communication(
        self,
        cluster_index: int,
        quality: DataQuality,
        last_seen_at: Optional[datetime] = None,
    ) -> None:
        with self._lock:
            cluster = self._cluster(cluster_index)
            cluster.communication_quality = DataQuality(quality)
            if last_seen_at is not None:
                cluster.last_seen_at = last_seen_at

    def replace_cluster_alarms(
        self,
        cluster_index: int,
        alarms: Sequence[ActiveAlarm],
    ) -> None:
        with self._lock:
            self._cluster(cluster_index).active_alarms = tuple(alarms)

    def get_cluster(self, cluster_index: int) -> ClusterNode:
        with self._lock:
            return deepcopy(self._cluster(cluster_index))

    def list_clusters(self) -> Iterable[ClusterNode]:
        with self._lock:
            stack = self._system.stacks[DEFAULT_STACK_ID]
            return tuple(
                deepcopy(stack.clusters[cluster_index])
                for cluster_index in sorted(stack.clusters)
            )

    def snapshot(self) -> SystemNode:
        with self._lock:
            return deepcopy(self._system)

    def clear_runtime_values(self) -> None:
        with self._lock:
            stack = self._system.stacks[DEFAULT_STACK_ID]
            for cluster in stack.clusters.values():
                cluster.latest_values.clear()
                cluster.active_alarms = ()
                cluster.communication_quality = DataQuality.UNKNOWN
                cluster.last_seen_at = None

    def _cluster(self, cluster_index: int) -> ClusterNode:
        stack = self._system.stacks[DEFAULT_STACK_ID]
        try:
            return stack.clusters[int(cluster_index)]
        except KeyError as exc:
            raise KeyError(f"Unknown cluster index: {cluster_index}") from exc

    @staticmethod
    def _next_statistics(previous: Optional[LatestValue], value) -> SignalStatistics:
        if not isinstance(value, (int, float)):
            return previous.statistics if previous is not None else SignalStatistics()
        numeric_value = float(value)
        if previous is None or previous.statistics.sample_count <= 0:
            return SignalStatistics(
                minimum=numeric_value,
                maximum=numeric_value,
                average=numeric_value,
                sample_count=1,
            )
        statistics = previous.statistics
        sample_count = statistics.sample_count + 1
        average = (
            float(statistics.average) * statistics.sample_count + numeric_value
        ) / sample_count
        return SignalStatistics(
            minimum=min(float(statistics.minimum), numeric_value),
            maximum=max(float(statistics.maximum), numeric_value),
            average=average,
            sample_count=sample_count,
        )
