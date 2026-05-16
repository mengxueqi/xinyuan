from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR if (CURRENT_DIR / "ui_app.py").exists() else CURRENT_DIR.parent
SITE_PACKAGES = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if SITE_PACKAGES.exists() and str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))

from streamlit.web import cli as streamlit_cli


def main() -> None:
    ui_script = PROJECT_ROOT / "ui_app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(ui_script),
        "--server.address=localhost",
        "--server.port=8510",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    main()
