from __future__ import annotations

from difflib import SequenceMatcher

from detectors.base import ChangeRecord


def detect_job_changes(
    current_snapshots: list[dict],
    previous_snapshots: list[dict],
) -> list[ChangeRecord]:
    previous_by_page = {
        _snapshot_key(snapshot): snapshot for snapshot in previous_snapshots
    }
    changes: list[ChangeRecord] = []

    for snapshot in current_snapshots:
        key = _snapshot_key(snapshot)
        previous = previous_by_page.get(key)
        if not previous:
            continue

        if snapshot.get("snapshot_hash") == previous.get("snapshot_hash"):
            continue

        before_text = previous.get("snapshot_text", "")
        after_text = snapshot.get("snapshot_text", "")
        similarity = SequenceMatcher(None, before_text, after_text).ratio()
        changed_ratio = round(1 - similarity, 4)

        changes.append(
            ChangeRecord(
                company_name=snapshot.get("company_name", "Unknown"),
                source_name=snapshot.get("source_name", ""),
                change_type="job_change",
                target_type="job_snapshot",
                title=snapshot.get("title", "(untitled jobs snapshot)"),
                summary=(
                    f"Jobs content changed for {snapshot.get('source_name', '')} "
                    f"with changed ratio {changed_ratio:.2%}"
                ),
                detected_at=snapshot.get("captured_at", ""),
                importance_score=65,
                url=snapshot.get("page_url"),
                before_value=_truncate(before_text),
                after_value=_truncate(after_text),
                changed_ratio=changed_ratio,
                metadata={
                    "page_url": snapshot.get("page_url"),
                    "job_signal_count": snapshot.get("metadata", {}).get(
                        "job_signal_count"
                    ),
                },
            )
        )

    return changes


def _snapshot_key(snapshot: dict) -> tuple[str, str, str]:
    return (
        snapshot.get("company_name", ""),
        snapshot.get("source_name", ""),
        snapshot.get("page_url", ""),
    )


def _truncate(text: str, limit: int = 500) -> str:
    return text[:limit]
