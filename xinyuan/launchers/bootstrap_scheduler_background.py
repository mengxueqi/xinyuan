from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR if (CURRENT_DIR / "scheduler.py").exists() else CURRENT_DIR.parent
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_FILE = LOG_DIR / "scheduler_runtime.log"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if SITE_PACKAGES.exists() and str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))

from scheduler import build_scheduler


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def main() -> None:
    scheduler = build_scheduler()
    log("Background scheduler starting.")
    for job in scheduler.get_jobs():
        log(f"Configured job: {job.id}")
    scheduler.start()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("Background scheduler crashed.")
        log(traceback.format_exc())
        raise
