from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from business_db import BusinessDatabase
from utils import get_logger, list_batch_keys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
BUSINESS_DB_PATH = DATA_DIR / "business" / "xinyuan.db"
COMPANIES_CSV = PROJECT_ROOT / "companies_core_seed.csv"
SOURCES_CSV = PROJECT_ROOT / "sources_seed.csv"
EVENTS_DIR = DATA_DIR / "processed" / "event_candidates"
CHANGES_DIR = DATA_DIR / "changes" / "change_logs"
INSIGHTS_DIR = DATA_DIR / "insights" / "insight_items"
LOG_DIR = DATA_DIR / "logs"


def sync_business_db(batch_keys: list[str] | None = None, logger=None) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    logger = logger or get_logger(LOG_DIR, "xinyuan.sync")
    logger.info("sync_business_db start | started_at=%s", started_at)

    database = BusinessDatabase(BUSINESS_DB_PATH)
    database.initialize()

    companies_count = database.seed_companies(COMPANIES_CSV)
    sources_count = database.seed_sources(SOURCES_CSV)
    if batch_keys is None:
        candidate_batches = sorted(
            set(list_batch_keys(EVENTS_DIR))
            | set(list_batch_keys(CHANGES_DIR))
            | set(list_batch_keys(INSIGHTS_DIR))
        )
        completed_batches = set(database.fetch_completed_batch_keys("sync_business_db"))
        target_batch_keys = [key for key in candidate_batches if key not in completed_batches]
    else:
        target_batch_keys = batch_keys

    batch_counts: dict[str, dict[str, int]] = {}
    for batch_key in target_batch_keys:
        event_count = database.sync_events_batch(EVENTS_DIR, batch_key)
        change_count = database.sync_change_logs_batch(CHANGES_DIR, batch_key)
        insight_count = database.sync_insight_items_batch(INSIGHTS_DIR, batch_key)
        batch_counts[batch_key] = {
            "events": event_count,
            "changes": change_count,
            "insights": insight_count,
        }
        logger.info(
            "Database sync batch complete | batch=%s | events=%s | changes=%s | insights=%s",
            batch_key,
            event_count,
            change_count,
            insight_count,
        )

    logger.info(
        "Business database sync complete | companies=%s | sources=%s | synced_batches=%s",
        companies_count,
        sources_count,
        len(batch_counts),
    )
    return {
        "companies": companies_count,
        "sources": sources_count,
        "synced_batches": sorted(batch_counts),
        "batch_counts": batch_counts,
        "skipped": not bool(batch_counts),
    }
