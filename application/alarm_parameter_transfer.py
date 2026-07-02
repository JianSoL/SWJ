from collections import deque
import time


class AlarmParameterTransfer:
    """Non-blocking request, write, retry, and verification state machine."""

    SUMMARY_FIELD_INDICES = tuple(range(10))

    def __init__(
        self,
        base_id,
        alarm_count,
        field_count=30,
        response_timeout_s=0.45,
        max_retries=2,
    ):
        self.base_id = int(base_id)
        self.alarm_count = int(alarm_count)
        self.field_count = int(field_count)
        self.response_timeout_s = float(response_timeout_s)
        self.max_retries = int(max_retries)
        self.cache = {}
        self.cancel()

    def cancel(self):
        self.operation = "idle"
        self.phase = "idle"
        self.queue = deque()
        self.pending = {}
        self.expected = {}
        self.failures = {}
        self.completed_count = 0
        self.total_count = 0
        self.target_alarm_id = None

    def _start(self, operation, actions, target_alarm_id=None, expected=None, total_count=None):
        self.operation = str(operation)
        self.phase = "write" if operation == "write" else str(operation)
        self.queue = deque(actions)
        self.pending = {}
        self.expected = dict(expected or {})
        self.failures = {}
        self.completed_count = 0
        self.total_count = len(actions) if total_count is None else int(total_count)
        self.target_alarm_id = target_alarm_id
        self._advance_phase_if_ready()

    def start_summary(self, alarm_ids):
        actions = []
        for alarm_id in alarm_ids:
            for field_index in self.SUMMARY_FIELD_INDICES:
                actions.append(self._action("read", alarm_id, field_index))
        self._start("summary", actions)

    def start_detail(self, alarm_id):
        alarm_id = int(alarm_id)
        actions = [self._action("read", alarm_id, field_index) for field_index in range(self.field_count)]
        self._start("detail", actions, target_alarm_id=alarm_id)

    def start_write(self, alarm_id, raw_fields):
        alarm_id = int(alarm_id)
        expected = {}
        actions = []
        for field_index, raw_value in sorted((raw_fields or {}).items()):
            data_id = self.data_id(alarm_id, field_index)
            raw_value = int(raw_value) & 0xFFFF
            expected[data_id] = raw_value
            actions.append(
                {
                    "kind": "write",
                    "data_id": data_id,
                    "alarm_id": alarm_id,
                    "field_index": int(field_index),
                    "value": raw_value,
                    "retries": 0,
                }
            )
        self._start(
            "write",
            actions,
            target_alarm_id=alarm_id,
            expected=expected,
            total_count=len(actions) * 2,
        )

    def _action(self, kind, alarm_id, field_index, value=None, retries=0):
        return {
            "kind": str(kind),
            "data_id": self.data_id(alarm_id, field_index),
            "alarm_id": int(alarm_id),
            "field_index": int(field_index),
            "value": value,
            "retries": int(retries),
        }

    def data_id(self, alarm_id, field_index):
        return self.base_id + int(alarm_id) * 32 + int(field_index)

    def decode_data_id(self, data_id):
        offset = int(data_id) - self.base_id
        if offset < 0:
            return None
        alarm_id, field_index = divmod(offset, 32)
        if not (0 <= alarm_id < self.alarm_count and 0 <= field_index < self.field_count):
            return None
        return alarm_id, field_index

    def is_alarm_data_id(self, data_id):
        return self.decode_data_id(data_id) is not None

    def next_actions(self, now=None, burst=3, max_in_flight=12):
        if self.phase in ("idle", "complete", "cancelled"):
            return []
        now = time.monotonic() if now is None else float(now)
        self._expire_pending(now)
        self._advance_phase_if_ready()
        actions = []
        capacity = max(0, int(max_in_flight) - len(self.pending))
        send_count = min(max(0, int(burst)), capacity, len(self.queue))
        for _index in range(send_count):
            action = self.queue.popleft()
            action["sent_at"] = now
            self.pending[action["data_id"]] = action
            actions.append(dict(action))
        return actions

    def _expire_pending(self, now):
        expired_ids = [
            data_id
            for data_id, action in self.pending.items()
            if now - float(action.get("sent_at", now)) >= self.response_timeout_s
        ]
        for data_id in expired_ids:
            action = self.pending.pop(data_id)
            self._retry_or_fail(action, "响应超时")

    def _retry_or_fail(self, action, reason):
        if int(action.get("retries", 0)) < self.max_retries:
            action = dict(action)
            action["retries"] = int(action.get("retries", 0)) + 1
            action.pop("sent_at", None)
            self.queue.appendleft(action)
            return
        self.failures[action["data_id"]] = str(reason)
        self.completed_count += 1

    def accept_read(self, data_id, raw_value, success=True):
        decoded = self.decode_data_id(data_id)
        if decoded is None:
            return None
        alarm_id, field_index = decoded
        action = self.pending.pop(int(data_id), None)
        if action is not None and action.get("kind") != "read":
            self.pending[int(data_id)] = action
            action = None

        raw_value = int(raw_value) & 0xFFFF
        if success:
            self.cache.setdefault(alarm_id, {})[field_index] = raw_value
            if action is not None:
                self.completed_count += 1
            if self.phase == "verify" and int(data_id) in self.expected:
                expected = self.expected[int(data_id)]
                if raw_value == expected:
                    self.failures.pop(int(data_id), None)
                else:
                    self.failures[int(data_id)] = f"回读0x{raw_value:04X}，期望0x{expected:04X}"
        elif action is not None:
            self._retry_or_fail(action, "下位机读取失败")

        self._advance_phase_if_ready()
        return {
            "alarm_id": alarm_id,
            "field_index": field_index,
            "raw_value": raw_value,
            "success": bool(success),
            "record_complete": self.is_record_complete(alarm_id),
        }

    def accept_write(self, data_id, success=True):
        action = self.pending.pop(int(data_id), None)
        if action is None or action.get("kind") != "write":
            return False
        if success:
            self.completed_count += 1
        else:
            self._retry_or_fail(action, "下位机拒绝写入")
        self._advance_phase_if_ready()
        return True

    def _advance_phase_if_ready(self):
        if self.queue or self.pending:
            return
        if self.phase == "write":
            self.phase = "verify"
            for data_id, raw_value in self.expected.items():
                decoded = self.decode_data_id(data_id)
                if decoded is None:
                    continue
                alarm_id, field_index = decoded
                self.queue.append(self._action("read", alarm_id, field_index, value=raw_value))
            if not self.queue:
                self.phase = "complete"
        elif self.phase not in ("idle", "complete", "cancelled"):
            self.phase = "complete"

    def is_record_complete(self, alarm_id):
        fields = self.cache.get(int(alarm_id), {})
        return all(field_index in fields for field_index in range(self.field_count))

    def raw_record(self, alarm_id):
        fields = self.cache.get(int(alarm_id), {})
        return [int(fields.get(field_index, 0)) & 0xFFFF for field_index in range(self.field_count)]

    def progress(self):
        return {
            "operation": self.operation,
            "phase": self.phase,
            "completed": min(self.completed_count, self.total_count),
            "total": self.total_count,
            "failed": len(self.failures),
            "pending": len(self.pending),
            "queued": len(self.queue),
            "target_alarm_id": self.target_alarm_id,
        }

    def is_busy(self):
        return self.phase not in ("idle", "complete", "cancelled")
