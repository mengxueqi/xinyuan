from detectors.base import ChangeRecord
from detectors.events import detect_new_events
from detectors.jobs import detect_job_changes
from detectors.pages import detect_page_changes

__all__ = [
    "ChangeRecord",
    "detect_job_changes",
    "detect_new_events",
    "detect_page_changes",
]
