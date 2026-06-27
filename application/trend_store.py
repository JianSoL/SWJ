import math
import threading
from collections import deque
from dataclasses import dataclass, replace


DEFAULT_PERIODS = (1, 5, 10, 30, 60)
DEFAULT_METRICS = ("voltage", "current")


@dataclass(frozen=True)
class TrendBar:
    bucket_start: float
    first: float
    maximum: float
    minimum: float
    latest: float
    sample_count: int


def aggregate_period_statistics(samples, period_seconds, max_bars=None):
    period_seconds = max(1, int(period_seconds))
    buckets = {}
    for timestamp, value in sorted(samples or (), key=lambda item: item[0]):
        try:
            timestamp = float(timestamp)
            value = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(timestamp) or not math.isfinite(value):
            continue
        bucket_start = math.floor(timestamp / period_seconds) * period_seconds
        current = buckets.get(bucket_start)
        if current is None:
            buckets[bucket_start] = [value, value, value, value, 1]
        else:
            current[1] = max(current[1], value)
            current[2] = min(current[2], value)
            current[3] = value
            current[4] += 1

    bars = [
        TrendBar(bucket, values[0], values[1], values[2], values[3], values[4])
        for bucket, values in sorted(buckets.items())
    ]
    if max_bars is not None:
        bars = bars[-max(1, int(max_bars)):]
    return bars


class _MetricState:
    def __init__(self, periods, max_bars):
        self.sample_count = 0
        self.last_timestamp = None
        self.latest_value = None
        self.revision = 0
        self.bars_by_period = {
            period: deque(maxlen=max_bars)
            for period in periods
        }


class TrendDataStore:
    """Bounded, incremental time-series storage shared by protocol and UI layers."""

    def __init__(
        self,
        metrics=DEFAULT_METRICS,
        periods=DEFAULT_PERIODS,
        max_bars_per_period=480,
    ):
        self.metrics = tuple(dict.fromkeys(str(metric) for metric in metrics))
        self.periods = tuple(sorted({max(1, int(period)) for period in periods}))
        self.max_bars_per_period = max(1, int(max_bars_per_period))
        self._clusters = {}
        self._lock = threading.RLock()

    def add_sample(self, cluster_index, metric, value, timestamp):
        try:
            cluster_index = int(cluster_index)
            metric = str(metric)
            value = float(value)
            timestamp = float(timestamp)
        except (TypeError, ValueError):
            return False
        if cluster_index <= 0 or metric not in self.metrics:
            return False
        if not math.isfinite(value) or not math.isfinite(timestamp):
            return False

        with self._lock:
            state = self._metric_state(cluster_index, metric)
            if state.last_timestamp is not None and timestamp < state.last_timestamp:
                timestamp = state.last_timestamp
            state.last_timestamp = timestamp
            state.latest_value = value
            state.sample_count += 1
            state.revision += 1
            for period, bars in state.bars_by_period.items():
                bucket_start = math.floor(timestamp / period) * period
                if bars and bars[-1].bucket_start == bucket_start:
                    current = bars[-1]
                    bars[-1] = replace(
                        current,
                        maximum=max(current.maximum, value),
                        minimum=min(current.minimum, value),
                        latest=value,
                        sample_count=current.sample_count + 1,
                    )
                else:
                    bars.append(
                        TrendBar(
                            bucket_start=bucket_start,
                            first=value,
                            maximum=value,
                            minimum=value,
                            latest=value,
                            sample_count=1,
                        )
                    )
        return True

    def bars_for(self, cluster_index, metric, period_seconds, max_bars=None):
        try:
            cluster_index = int(cluster_index)
            metric = str(metric)
            period_seconds = max(1, int(period_seconds))
        except (TypeError, ValueError):
            return []
        with self._lock:
            state = self._existing_metric_state(cluster_index, metric)
            if state is None:
                return []
            bars = state.bars_by_period.get(period_seconds)
            if bars is None:
                return []
            result = list(bars)
        if max_bars is not None:
            result = result[-max(1, int(max_bars)):]
        return result

    def sample_count(self, cluster_index, metric):
        with self._lock:
            state = self._existing_metric_state(int(cluster_index), str(metric))
            return 0 if state is None else state.sample_count

    def latest_value(self, cluster_index, metric):
        with self._lock:
            state = self._existing_metric_state(int(cluster_index), str(metric))
            return None if state is None else state.latest_value

    def revision(self, cluster_index, metric):
        with self._lock:
            state = self._existing_metric_state(int(cluster_index), str(metric))
            return 0 if state is None else state.revision

    def clear_cluster(self, cluster_index):
        with self._lock:
            self._clusters.pop(int(cluster_index), None)

    def memory_stats(self):
        with self._lock:
            metric_count = 0
            bar_count = 0
            sample_count = 0
            for metrics in self._clusters.values():
                metric_count += len(metrics)
                for state in metrics.values():
                    sample_count += state.sample_count
                    bar_count += sum(len(bars) for bars in state.bars_by_period.values())
            return {
                "cluster_count": len(self._clusters),
                "metric_count": metric_count,
                "bar_count": bar_count,
                "sample_count": sample_count,
                "max_bars_per_period": self.max_bars_per_period,
            }

    def _metric_state(self, cluster_index, metric):
        metrics = self._clusters.setdefault(cluster_index, {})
        state = metrics.get(metric)
        if state is None:
            state = _MetricState(self.periods, self.max_bars_per_period)
            metrics[metric] = state
        return state

    def _existing_metric_state(self, cluster_index, metric):
        return self._clusters.get(cluster_index, {}).get(metric)
