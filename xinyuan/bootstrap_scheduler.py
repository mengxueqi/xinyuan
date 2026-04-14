from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if SITE_PACKAGES.exists() and str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))

from scheduler import build_scheduler, print_job_summary


def main() -> None:
    scheduler = build_scheduler()
    print_job_summary(scheduler)
    print("Scheduler started. Press Ctrl+C to stop.")
    scheduler.start()


if __name__ == "__main__":
    main()
