from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from insights import InsightRecord, build_reason, score_change, summarize_change
from storage import LocalInsightStorage
from utils import get_logger, pending_batch_keys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHANGE_LOGS_DIR = PROJECT_ROOT / "data" / "changes" / "change_logs"
INSIGHTS_DIR = PROJECT_ROOT / "data" / "insights"
LOG_DIR = PROJECT_ROOT / "data" / "logs"


def load_change_batches(change_logs_dir: Path = CHANGE_LOGS_DIR) -> dict[str, list[dict]]:
    batches: dict[str, list[dict]] = {}
    if not change_logs_dir.exists():
        return batches

    for file_path in sorted(change_logs_dir.glob("*.jsonl")):
        rows = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        batches[file_path.stem] = rows

    return batches


def priority_from_score(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def build_insights(batch_keys: list[str] | None = None, logger=None) -> dict[str, Any]:
    run_started_at = datetime.now()
    logger = logger or get_logger(LOG_DIR, "xinyuan.insights")
    logger.info("build_insights start")

    target_batch_keys = batch_keys or pending_batch_keys(
        CHANGE_LOGS_DIR,
        INSIGHTS_DIR / "insight_runs",
    )
    batches = load_change_batches()
    if not batches:
        logger.info("No change logs found. Skipping insight generation.")
        return {"processed_batches": [], "batch_counts": {}, "skipped": True}

    storage = LocalInsightStorage(INSIGHTS_DIR)
    batch_counts: dict[str, dict[str, int]] = {}

    for batch_key in target_batch_keys:
        changes = batches.get(batch_key, [])
        if batch_key not in batches:
            continue
        insights: list[InsightRecord] = []
        for change in changes:
            score, score_reasons = score_change(change)
            insights.append(
                InsightRecord(
                    company_name=change.get("company_name", "Unknown"),
                    source_name=change.get("source_name", ""),
                    change_type=change.get("change_type", ""),
                    target_type=change.get("target_type", ""),
                    title=change.get("title", ""),
                    summary=summarize_change(change),
                    importance_score=score,
                    reason=build_reason(change, score_reasons),
                    detected_at=change.get("detected_at", batch_key),
                    priority_label=priority_from_score(score),
                    url=change.get("url"),
                    metadata=change.get("metadata", {}),
                )
            )

        counts = storage.write_batch(batch_key, insights, run_started_at)
        batch_counts[batch_key] = counts
        logger.info(
            "Insight build complete | batch=%s | insights=%s",
            batch_key,
            counts["insight_items"],
        )
    if not batch_counts:
        logger.info("No pending batches found for insight generation.")
        return {"processed_batches": [], "batch_counts": {}, "skipped": True}
    return {
        "processed_batches": sorted(batch_counts),
        "batch_counts": batch_counts,
        "skipped": False,
    }
