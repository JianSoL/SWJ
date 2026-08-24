"""Domain-neutral runtime models shared by application services.

The hierarchy follows the maintainable product model used by the studio:
System -> Stack -> Cluster -> BMU -> Cell.  Protocol-specific indexes and Qt
types deliberately do not belong in this module.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class DataQuality(str, Enum):
    """Quality attached to every latest value in the runtime cache."""

    UNKNOWN = "unknown"
    GOOD = "good"
    STALE = "stale"
    OFFLINE = "offline"
    INVALID = "invalid"


@dataclass(frozen=True)
class SignalStatistics:
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    average: Optional[float] = None
    sample_count: int = 0


@dataclass(frozen=True)
class LatestValue:
    value: Any
    unit: str = ""
    quality: DataQuality = DataQuality.UNKNOWN
    timestamp: Optional[datetime] = None
    statistics: SignalStatistics = field(default_factory=SignalStatistics)


@dataclass(frozen=True)
class ActiveAlarm:
    code: str
    name: str
    level: int = 0
    timestamp: Optional[datetime] = None


@dataclass
class CellNode:
    cell_index: int
    latest_values: Dict[str, LatestValue] = field(default_factory=dict)


@dataclass
class BmuNode:
    bmu_index: int
    cells: Dict[int, CellNode] = field(default_factory=dict)
    latest_values: Dict[str, LatestValue] = field(default_factory=dict)


@dataclass
class ClusterNode:
    cluster_index: int
    address: str
    bmus: Dict[int, BmuNode] = field(default_factory=dict)
    latest_values: Dict[str, LatestValue] = field(default_factory=dict)
    active_alarms: Tuple[ActiveAlarm, ...] = ()
    communication_quality: DataQuality = DataQuality.UNKNOWN
    last_seen_at: Optional[datetime] = None


@dataclass
class StackNode:
    stack_id: str
    clusters: Dict[int, ClusterNode] = field(default_factory=dict)


@dataclass
class SystemNode:
    system_id: str
    stacks: Dict[str, StackNode] = field(default_factory=dict)
