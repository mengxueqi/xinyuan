from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from business_db import BusinessDatabase
from collectors import JobsCollector, RSSCollector, SourceConfig, WebCollector
from storage import LocalRawStorage
from utils import get_logger, make_batch_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_CSV = PROJECT_ROOT / "sources_seed.csv"
RAW_STORAGE_DIR = PROJECT_ROOT / "data" / "raw"
BUSINESS_DB_PATH = PROJECT_ROOT / "data" / "business" / "xinyuan.db"
LOG_DIR = PROJECT_ROOT / "data" / "logs"


def load_sources(csv_path: Path = SOURCES_CSV) -> list[SourceConfig]:
    sources: list[SourceConfig] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sources.append(
                SourceConfig(
                    company_name=row["company_name"],
                    source_name=row["source_name"],
                    source_type=row["source_type"],
                    url=row["url"],
                    parser_type=row.get("parser_type", "generic_web"),
                    crawl_frequency=row.get("crawl_frequency", "daily"),
                    is_active=row.get("is_active", "true").lower() == "true",
                    priority=row.get("priority", "medium"),
                    notes=row.get("notes", ""),
                )
            )
    return sources


def get_collector(source_type: str):
    collectors = {
        "rss": RSSCollector(),
        "web": WebCollector(),
        "jobs": JobsCollector(),
    }
    if source_type not in collectors:
        raise ValueError(f"Unsupported source type: {source_type}")
    return collectors[source_type]


def crawl_sources(batch_key: str | None = None, logger=None) -> dict[str, Any]:
    run_started_at = datetime.now()
    effective_batch_key = batch_key or make_batch_key(run_started_at)
    logger = logger or get_logger(LOG_DIR, "xinyuan.crawl")
    database = BusinessDatabase(BUSINESS_DB_PATH)
    database.initialize()

    logger.info(
        "crawl_sources start | batch=%s | started_at=%s",
        effective_batch_key,
        run_started_at.isoformat(timespec="seconds"),
    )
    sources = load_sources()
    active_sources = [source for source in sources if source.is_active]
    logger.info("Loaded %s active sources from %s", len(active_sources), SOURCES_CSV.name)
    raw_storage = LocalRawStorage(RAW_STORAGE_DIR)
    success_count = 0
    failure_count = 0
    stored_counts = {
        "raw_documents": 0,
        "page_snapshots": 0,
        "job_snapshots": 0,
    }
    failures: list[dict[str, str]] = []

    for source in active_sources:
        collector = get_collector(source.source_type)
        logger.info(
            "Crawling source | batch=%s | company=%s | source=%s | type=%s | url=%s",
            effective_batch_key,
            source.company_name,
            source.source_name,
            source.source_type,
            source.url,
        )
        try:
            items = collector.collect(source)
            counts = raw_storage.persist_items(
                source,
                items,
                run_started_at,
                batch_key=effective_batch_key,
            )
            success_count += 1
            for key in stored_counts:
                stored_counts[key] += counts[key]
            logger.info(
                "Crawl success | batch=%s | source=%s | items=%s | raw=%s | page=%s | jobs=%s",
                effective_batch_key,
                source.source_name,
                len(items),
                counts["raw_documents"],
                counts["page_snapshots"],
                counts["job_snapshots"],
            )
        except Exception as exc:
            failure_count += 1
            failures.append(
                {
                    "company_name": source.company_name,
                    "source_name": source.source_name,
                    "url": source.url,
                    "error": str(exc),
                }
            )
            logger.exception(
                "Crawl failed | batch=%s | source=%s | url=%s",
                effective_batch_key,
                source.source_name,
                source.url,
            )

    logger.info(
        "crawl_sources complete | batch=%s | success=%s | failure=%s | total=%s",
        effective_batch_key,
        success_count,
        failure_count,
        len(active_sources),
    )
    return {
        "batch_key": effective_batch_key,
        "success_count": success_count,
        "failure_count": failure_count,
        "total_sources": len(active_sources),
        "stored_counts": stored_counts,
        "failures": failures,
    }
