from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from insights import (
    InsightRecord,
    ProcessedEventRecord,
    build_event_reason,
    build_reason,
    build_score_basis,
    priority_from_score,
    score_change,
    score_event,
    summarize_change,
    summarize_event,
)
from storage import LocalInsightStorage
from utils import get_logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVENT_CANDIDATES_DIR = PROJECT_ROOT / "data" / "processed" / "event_candidates"
CHANGE_LOGS_DIR = PROJECT_ROOT / "data" / "changes" / "change_logs"
INSIGHTS_DIR = PROJECT_ROOT / "data" / "insights"
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


def build_insights(batch_keys: list[str] | None = None, logger=None) -> dict[str, Any]:
    run_started_at = datetime.now()
    logger = logger or get_logger(LOG_DIR, "xinyuan.insights")
    logger.info("build_insights start")

    event_batches = load_jsonl_batches(EVENT_CANDIDATES_DIR)
    change_batches = load_jsonl_batches(CHANGE_LOGS_DIR)
    available_batch_keys = sorted(set(event_batches) | set(change_batches))
    if not available_batch_keys:
        logger.info("No event or change batches found. Skipping processed-event build.")
        return {"processed_batches": [], "batch_counts": {}, "skipped": True}

    completed_batch_keys = set(load_jsonl_batches(INSIGHTS_DIR / "insight_runs"))
    target_batch_keys = batch_keys or [
        key for key in available_batch_keys if key not in completed_batch_keys
    ]
    if not target_batch_keys:
        logger.info("No pending batches found for processed-event build.")
        return {"processed_batches": [], "batch_counts": {}, "skipped": True}

    storage = LocalInsightStorage(INSIGHTS_DIR)
    batch_counts: dict[str, dict[str, int]] = {}

    for batch_key in target_batch_keys:
        events = event_batches.get(batch_key, [])
        changes = change_batches.get(batch_key, [])
        processed_events, insights = _build_batch_outputs(batch_key, events, changes)

        counts = storage.write_batch(batch_key, processed_events, insights, run_started_at)
        batch_counts[batch_key] = counts
        logger.info(
            "Processed-event build complete | batch=%s | processed_events=%s | analysis_items=%s",
            batch_key,
            counts["processed_events"],
            counts["insight_items"],
        )

    return {
        "processed_batches": sorted(batch_counts),
        "batch_counts": batch_counts,
        "skipped": False,
    }


def _build_batch_outputs(
    batch_key: str,
    events: list[dict],
    changes: list[dict],
) -> tuple[list[ProcessedEventRecord], list[InsightRecord]]:
    new_event_changes = {
        _change_identity(change): change
        for change in changes
        if change.get("change_type") == "new_event"
    }

    processed_events: list[ProcessedEventRecord] = []
    analysis_items: list[InsightRecord] = []

    for event in events:
        linked_change = new_event_changes.get(_event_identity(event))
        is_historically_new = linked_change is not None
        score, score_reasons = score_event(
            event,
            is_historically_new=is_historically_new,
            linked_change=linked_change,
        )
        summary = summarize_event(event, is_historically_new=is_historically_new)
        reason = build_event_reason(event, score_reasons)
        priority_label = priority_from_score(score)

        processed_event = ProcessedEventRecord(
            batch_date=batch_key,
            company_name=event.get("company_name", "Unknown"),
            source_name=event.get("source_name", ""),
            source_type=event.get("source_type", ""),
            url=event.get("url", ""),
            title=event.get("title", ""),
            content_text=event.get("content_text", ""),
            summary=summary,
            reason=reason,
            importance_score=score,
            priority_label=priority_label,
            published_at=event.get("published_at"),
            fetched_at=event.get("fetched_at"),
            is_historically_new=is_historically_new,
            linked_change_type=linked_change.get("change_type") if linked_change else None,
            event_types=list(event.get("event_types", [])),
            tech_signals=list(event.get("tech_signals", [])),
            matched_companies=list(event.get("matched_companies", [])),
            matched_focus_keywords=list(event.get("matched_focus_keywords", [])),
            metadata={
                "change_type": linked_change.get("change_type") if linked_change else None,
                "target_type": linked_change.get("target_type") if linked_change else "event",
                "published_at": event.get("published_at"),
                "score_basis": build_score_basis(score_reasons),
            },
        )
        processed_events.append(processed_event)

        if is_historically_new:
            analysis_items.append(
                InsightRecord(
                    company_name=processed_event.company_name,
                    source_name=processed_event.source_name,
                    change_type="new_event",
                    target_type="event",
                    title=processed_event.title,
                    summary=processed_event.summary,
                    importance_score=processed_event.importance_score,
                    reason=processed_event.reason,
                    detected_at=linked_change.get("detected_at", batch_key),
                    priority_label=processed_event.priority_label,
                    url=processed_event.url,
                    metadata={
                        **processed_event.metadata,
                        "event_types": processed_event.event_types,
                        "tech_signals": processed_event.tech_signals,
                        "matched_companies": processed_event.matched_companies,
                        "matched_focus_keywords": processed_event.matched_focus_keywords,
                        "is_historically_new": True,
                        "score_basis": build_score_basis(score_reasons),
                    },
                )
            )

    for change in changes:
        if change.get("change_type") == "new_event":
            continue
        score, score_reasons = score_change(change)
        analysis_items.append(
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
                metadata={
                    **change.get("metadata", {}),
                    "score_basis": build_score_basis(score_reasons),
                },
            )
        )

    return processed_events, analysis_items


def _event_identity(event: dict) -> tuple[str, str, str, str]:
    return (
        str(event.get("company_name") or ""),
        str(event.get("source_name") or ""),
        str(event.get("url") or ""),
        str(event.get("title") or ""),
    )


def _change_identity(change: dict) -> tuple[str, str, str, str]:
    return (
        str(change.get("company_name") or ""),
        str(change.get("source_name") or ""),
        str(change.get("url") or ""),
        str(change.get("title") or ""),
    )
