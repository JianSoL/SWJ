# CANFD Architecture

> The architecture is being migrated incrementally to the layered target in
> `../docs/system_architecture.md`. Naming and maintenance rules live in
> `../docs/coding_standards.md`. This file retains the detailed runtime and
> driver notes for the existing CAN implementation.

## Layering

The legacy CAN runtime is split into three primary layers. New product slices
add explicit application services, a unified data center, and protocol modules
without destabilizing the proven hardware path.

- Bottom layer: `infrastructure/cxcanfd_driver.py`
  - Wraps `ControlCANFD.dll` with the same open/init/start/send/receive/close sequence used by `cxcanfd_x64_v2.0.py`
  - Owns all `ctypes` structures and DLL calls
  - Does not know any BCU request protocol, DBC rule, or Qt widget
- Application layer: `application/can_service.py`
  - Owns request/response protocol, periodic DBC decoding, cluster state, and logging
  - Converts raw CAN/CANFD frames into `LegacySignalUpdate` and `PeriodicSignalUpdate`
  - Depends on domain models and the driver abstraction only
- UI layer: `presentation/main_window.py`
  - Owns Qt timers, tabs, tables, and view refresh
  - Calls application services and renders returned updates
  - Does not call the DLL directly

## Composition Root

`main.py` is the only composition root.

- Resolves runtime files through `application/runtime.py`
- Loads runtime config from `conf.yaml`
- Loads the legacy signal catalog from `SINGLE/BCU.yaml`
- Loads the periodic DBC runtime from `DCFDV1.3.dbc`
- Creates `SessionLogManager`
- Creates `CxCanFdDriver`
- Creates `CanApplicationService`
- Creates `MainWindow`

The runtime dependency direction is strictly one-way:

`presentation -> application -> domain/infrastructure`

`infrastructure` never imports `presentation`, and `application` never imports Qt.

## High-throughput Data Pipeline

The receive path uses bounded work instead of one fixed receive call per UI tick.

1. `CxCanFdDriver` reuses CAN and CAN FD `ctypes` receive buffers.
2. `CanApplicationService.poll()` drains multiple batches up to a frame limit and a
   wall-clock budget, so bursts are consumed without starving the Qt event loop.
3. Repeated updates in one poll are coalesced by signal identity. The UI receives
   only the newest value while service caches and raw logs still process every frame.
4. Data polling and widget rendering use separate rates. Active pages collect every
   10 ms while expensive value grids render the newest snapshot every 50 ms.
5. `SessionLogManager` batches CSV flushes by row count or elapsed time. The regular
   snapshot timer explicitly flushes all writers to preserve one-second durability.
6. The service tracks TX/RX activity per cluster. The overview distinguishes adapter
   connection from live BCU traffic and reports waiting, active, and receive-timeout
   states without coupling protocol counters to Qt widgets.

Runtime tuning is available in `conf.yaml`:

- `RX_BATCH_SIZE`
- `RX_MAX_FRAMES_PER_POLL`
- `RX_POLL_BUDGET_MS`
- `ACTIVE_POLL_INTERVAL_MS`
- `POLL_INTERVAL_MS`
- `QUERY_INTERVAL_MS`
- `BACKGROUND_QUERY_INTERVAL_MS`
- `ACTIVE_QUERY_BURST_SIZE`
- `UI_REFRESH_INTERVAL_MS`
- `COMMUNICATION_TILE_REFRESH_MS`
- `COMMUNICATION_ACTIVE_TIMEOUT_MS`
- `LOG_FLUSH_INTERVAL_MS`
- `LOG_FLUSH_ROW_COUNT`

## Product Runtime Boundary

`application/runtime.py` centralizes product runtime paths and release resources.

- Source mode reads resources from the repository tree.
- PyInstaller mode prefers resources extracted under `sys._MEIPASS`.
- Logs default to `CANFD/log` in source mode and to `log` beside the EXE in frozen mode.
- `DCBMS_PROFILE` selects the `conf.yaml` profile.
- `DCBMS_LOG_DIR` overrides the log output directory.

The repository root `main.py` is now a launcher for the real `CANFD/main.py` entrypoint.
Release validation lives in `scripts/release_check.ps1`.

## Driver Decision

The old project driver path is no longer used by the new startup path.

- Active driver: `infrastructure/cxcanfd_driver.py`
- Official reference: `../cxcanfd_x64_v2.0.py`
- Deprecated historical files kept only for comparison:
  - `official_canfd.py`
  - `ZLGCanControl.py`

## Test Matrix

Automated tests:

- `tests/test_cxcanfd_driver.py`
  - Verifies DLL open/send/receive/close flow with a fake DLL
- `tests/test_can_service.py`
  - Verifies legacy request decoding, periodic DBC decoding, and logging behavior
- `tests/test_main_window.py`
  - Verifies UI creation, timer-driven refresh, and close cleanup
- `tests/test_bootstrap.py`
  - Verifies `main.py` assembles the new layered stack and does not route through the old driver

Manual hardware smoke:

- `tests/manual_hardware_smoke.py`
  - Opens the CANFD adapter
  - Sends one legacy A0 query
  - Polls both CAN and CANFD channels for a fixed duration
  - Prints frame counters and sample IDs
  - Closes the device cleanly

## Run

Visible UI:

```powershell
cd CANFD
C:\Users\ch\.conda\envs\QT\python.exe main.py
```

Automated tests:

```powershell
cd CANFD
$env:QT_QPA_PLATFORM='offscreen'
C:\Users\ch\.conda\envs\QT\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Manual hardware smoke:

```powershell
cd CANFD
C:\Users\ch\.conda\envs\QT\python.exe tests\manual_hardware_smoke.py
```
