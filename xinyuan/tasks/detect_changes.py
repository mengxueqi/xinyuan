from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from detectors import detect_job_changes, detect_new_events, detect_page_changes
from storage import LocalChangeStorage
from utils import get_logger, pending_batch_keys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVENT_CANDIDATES_DIR = PROJECT_ROOT / "data" / "processed" / "event_candidates"
PAGE_SNAPSHOTS_DIR = PROJECT_ROOT / "data" / "raw" / "page_snapshots"
JOB_SNAPSHOTS_DIR = PROJECT_ROOT / "data" / "raw" / "job_snapshots"
CHANGES_DIR = PROJECT_ROOT / "data" / "changes"
LOG_DIR = PROJECT_ROOT / "data" / "logs"


def load_jsonl_batches(directory: Path) -> dict[str, list[dict]]:
    batches: dict[str, list[dict]] = {}
    if not directory.exists():
        return batches

    for file_path in sorted(directory.glob("*.jsonl")):
        rows = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        batches[file_path.stem] = rows
    return batches


def get_previous_batch_key(
    available_batch_keys: list[str], current_batch_key: str
) -> str | None:
    prior_batch_keys = [
        batch_key for batch_key in available_batch_keys if batch_key < current_batch_key
    ]
    return prior_batch_keys[-1] if prior_batch_keys else None


def detect_changes(batch_keys: list[str] | None = None, logger=None) -> dict[str, Any]:
    run_started_at = datetime.now()
    logger = logger or get_logger(LOG_DIR, "xinyuan.detect")
    logger.info("detect_changes start")

    event_batches = load_jsonl_batches(EVENT_CANDIDATES_DIR)
    page_batches = load_jsonl_batches(PAGE_SNAPSHOTS_DIR)
    job_batches = load_jsonl_batches(JOB_SNAPSHOTS_DIR)

    available_batch_keys = sorted(
        set(event_batches.keys()) | set(page_batches.keys()) | set(job_batches.keys())
    )
    if not available_batch_keys:
        logger.info("No processed or snapshot batches found. Skipping change detection.")
        return {"processed_batches": [], "batch_counts": {}, "skipped": True}

    target_batch_keys = batch_keys or pending_batch_keys(
        EVENT_CANDIDATES_DIR,
        CHANGES_DIR / "detection_runs",
    )
    target_batch_keys = [key for key in target_batch_keys if key in available_batch_keys]
    if not target_batch_keys:
        logger.info("No pending batches found for change detection.")
        return {"processed_batches": [], "batch_counts": {}, "skipped": True}

    change_storage = LocalChangeStorage(CHANGES_DIR)
    batch_counts: dict[str, dict[str, int]] = {}

    for batch_key in target_batch_keys:
        previous_batch_key = get_previous_batch_key(available_batch_keys, batch_key)
        previous_event_batch_key = get_previous_batch_key(sorted(event_batches.keys()), batch_key)
        if not previous_batch_key:
            logger.info("Change detection skipped compare | batch=%s | reason=no_previous_batch", batch_key)
            counts = change_storage.write_batch(batch_key, [], run_started_at)
            batch_counts[batch_key] = counts
            continue

        changes = []
        previous_known_sources = {
            (
                row.get("company_name", "Unknown"),
                row.get("source_name", ""),
            )
            for row in event_batches.get(previous_event_batch_key or previous_batch_key, [])
            if row.get("source_name")
        }
        changes.extend(
            detect_new_events(
                batch_key,
                event_batches.get(batch_key, []),
                event_batches.get(previous_event_batch_key or previous_batch_key, []),
                previous_known_sources=previous_known_sources,
            )
        )
        changes.extend(
            detect_page_changes(
                page_batches.get(batch_key, []),
                page_batches.get(previous_batch_key, []),
            )
        )
        changes.extend(
            detect_job_changes(
                job_batches.get(batch_key, []),
                job_batches.get(previous_batch_key, []),
            )
        )

        counts = change_storage.write_batch(batch_key, changes, run_started_at)
        batch_counts[batch_key] = counts
        logger.info(
            "Change detection complete | batch=%s | previous=%s | changes=%s",
            batch_key,
            previous_batch_key,
            counts["change_logs"],
        )
    return {
        "processed_batches": sorted(batch_counts),
        "batch_counts": batch_counts,
        "skipped": False,
    }
