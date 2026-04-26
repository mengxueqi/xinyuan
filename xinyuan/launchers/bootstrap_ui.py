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

from streamlit.web.bootstrap import run as streamlit_run


def main() -> None:
    ui_script = PROJECT_ROOT / "ui_app.py"
    streamlit_run(
        str(ui_script),
        False,
        [],
        {
            "server.headless": True,
            "browser.gatherUsageStats": False,
            "global.developmentMode": False,
            "server.address": "localhost",
            "server.port": 8501,
            "browser.serverAddress": "localhost",
        },
    )


if __name__ == "__main__":
    main()
