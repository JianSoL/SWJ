"""Stable application facade for device-oriented UI workflows."""


class DeviceService:
    """Coordinates protocol polling with the unified runtime data center.

    Existing pages still use methods implemented by the legacy CAN protocol
    adapter.  ``__getattr__`` is an intentional migration boundary: new pages
    must use explicit application services, while old pages remain operational
    until they are migrated one at a time.
    """

    def __init__(self, protocol_service, dashboard_service):
        self.protocol_service = protocol_service
        self.dashboard_service = dashboard_service

    @property
    def cluster_indices(self):
        return self.protocol_service.cluster_indices

    @property
    def cluster_addresses(self):
        return self.protocol_service.cluster_addresses

    @property
    def snapshot_logging_enabled(self):
        return self.protocol_service.snapshot_logging_enabled

    def open(self):
        result = self.protocol_service.open()
        self.dashboard_service.refresh_all_clusters()
        return result

    def reopen(self, bus_config=None):
        result = self.protocol_service.reopen(bus_config=bus_config)
        self.dashboard_service.reset()
        return result

    def close(self):
        return self.protocol_service.close()

    def poll(self):
        result = self.protocol_service.poll()
        self.dashboard_service.ingest_poll_result(result)
        return result

    def update_runtime_config(self, updates):
        result = self.protocol_service.update_runtime_config(updates)
        self.dashboard_service.reconfigure()
        return result

    def send_next_dashboard_query(self):
        return self.dashboard_service.send_next_query()

    def refresh_dashboard(self):
        self.dashboard_service.refresh_all_clusters()
        return self.dashboard_service.get_dashboard()

    def get_dashboard(self):
        return self.dashboard_service.get_dashboard()

    def __getattr__(self, name):
        return getattr(self.protocol_service, name)
