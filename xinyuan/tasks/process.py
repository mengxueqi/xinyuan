from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from processors import (
    KeywordRegistry,
    classify_document,
    mark_duplicates,
    normalize_raw_document,
)
from storage import LocalProcessedStorage
from utils import get_logger, pending_batch_keys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DOCUMENTS_DIR = PROJECT_ROOT / "data" / "raw" / "raw_documents"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SEEDS_DIR = PROJECT_ROOT / "seeds"
KEYWORDS_CSV = SEEDS_DIR / "keywords_seed.csv"
LOG_DIR = PROJECT_ROOT / "data" / "logs"


def load_raw_documents(
    raw_documents_dir: Path = RAW_DOCUMENTS_DIR,
    batch_keys: list[str] | None = None,
) -> dict[str, list[dict]]:
    batches: dict[str, list[dict]] = {}
    if not raw_documents_dir.exists():
        return batches

    selected_batch_keys = set(batch_keys or [])
    for file_path in sorted(raw_documents_dir.glob("*.jsonl")):
        if selected_batch_keys and file_path.stem not in selected_batch_keys:
            continue
        rows = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        batches[file_path.stem] = rows

    return batches


def process_documents(batch_keys: list[str] | None = None, logger=None) -> dict[str, Any]:
    run_started_at = datetime.now()
    logger = logger or get_logger(LOG_DIR, "xinyuan.process")
    target_batch_keys = batch_keys or pending_batch_keys(
        RAW_DOCUMENTS_DIR,
        PROCESSED_DIR / "processing_runs",
    )
    logger.info(
        "process_documents start | requested_batches=%s",
        ",".join(target_batch_keys) if target_batch_keys else "(none)",
    )

    batches = load_raw_documents(batch_keys=target_batch_keys)
    if not batches:
        logger.info("No pending raw document batches found. Skipping processing.")
        return {"processed_batches": [], "batch_counts": {}, "skipped": True}

    registry = KeywordRegistry.from_csv(KEYWORDS_CSV)
    processed_storage = LocalProcessedStorage(PROCESSED_DIR)
    batch_counts: dict[str, dict[str, int]] = {}

    for batch_key, raw_documents in batches.items():
        logger.info(
            "Processing batch | batch=%s | raw_documents=%s",
            batch_key,
            len(raw_documents),
        )
        documents = [normalize_raw_document(raw_document) for raw_document in raw_documents]
        documents = mark_duplicates(documents)
        documents = [registry.match_document(document) for document in documents]
        documents = [
            classify_document(document, registry) for document in documents
        ]

        counts = processed_storage.write_batch(batch_key, documents, run_started_at)
        batch_counts[batch_key] = counts
        logger.info(
            "Processed batch complete | batch=%s | clean=%s | event_candidates=%s",
            batch_key,
            counts["clean_documents"],
            counts["event_candidates"],
        )
    return {
        "processed_batches": sorted(batch_counts),
        "batch_counts": batch_counts,
        "skipped": False,
    }
