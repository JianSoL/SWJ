# CANFD Architecture

## Layering

The CANFD application is now split into three explicit layers.

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

- Loads runtime config from `conf.yaml`
- Loads the legacy signal catalog from `SINGLE/BCU.xlsx`
- Loads the periodic DBC runtime from `DCFDV1.3.dbc`
- Creates `SessionLogManager`
- Creates `CxCanFdDriver`
- Creates `CanApplicationService`
- Creates `MainWindow`

The runtime dependency direction is strictly one-way:

`presentation -> application -> domain/infrastructure`

`infrastructure` never imports `presentation`, and `application` never imports Qt.

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
