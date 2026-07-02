import os
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]


CORE_PYTHON_FILES = [
    "main.py",
    "ZLGCanControl.py",
    "session_logger.py",
    "application/__init__.py",
    "application/configuration.py",
    "application/alarm_parameter_transfer.py",
    "application/dbc_parser.py",
    "application/index_catalog.py",
    "application/power_diagnostics.py",
    "application/trend_store.py",
    "UI/Q14.py",
    "UI/responsive.py",
    "UI/T24.py",
    "UI/T28.py",
    "UI/index_browser_dialog.py",
    "UI/T34.py",
    "UI/T36.py",
    "UI/T37.py",
    "UI/T38.py",
    "UI/T39.py",
    "scripts/can_smoke.py",
    "scripts/performance_check.py",
    "scripts/generate_index_catalog.py",
    "scripts/self_test.py",
]


def run_step(name, command, env=None):
    print(f"== {name}")
    result = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def main():
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    run_step(
        "py_compile",
        [sys.executable, "-m", "py_compile", *CORE_PYTHON_FILES],
        env=env,
    )
    run_step(
        "self_test",
        [sys.executable, "scripts/self_test.py"],
        env=env,
    )
    run_step(
        "performance_check",
        [sys.executable, "scripts/performance_check.py"],
        env=env,
    )
    print("RELEASE_CHECK_OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"RELEASE_CHECK_FAILED: {exc}")
        sys.exit(1)
