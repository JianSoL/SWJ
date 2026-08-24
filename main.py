from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent
CANFD_DIR = REPO_ROOT / "CANFD"

if str(CANFD_DIR) not in sys.path:
    sys.path.insert(0, str(CANFD_DIR))

from CANFD.main import main


if __name__ == "__main__":
    raise SystemExit(main())
