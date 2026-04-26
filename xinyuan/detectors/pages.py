from __future__ import annotations

from difflib import SequenceMatcher

from detectors.base import ChangeRecord

BLOCKED_SOURCE_NAME_HINTS = ("股票页", "财务摘要页", "公司公告页（股票）")
BLOCKED_URL_HINTS = ("sina.com.cn",)


def detect_page_changes(
    current_snapshots: list[dict],
    previous_snapshots: list[dict],
) -> list[ChangeRecord]:
    previous_by_page = {
        _snapshot_key(snapshot): snapshot for snapshot in previous_snapshots
    }
    changes: list[ChangeRecord] = []

    for snapshot in current_snapshots:
        if _is_blocked_page_snapshot(snapshot):
            continue
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

        if changed_ratio < 0.05:
            continue

        changes.append(
            ChangeRecord(
                company_name=snapshot.get("company_name", "Unknown"),
                source_name=snapshot.get("source_name", ""),
                change_type="page_change",
                target_type="page",
                title=snapshot.get("title", "(untitled page snapshot)"),
                summary=(
                    f"Page content changed for {snapshot.get('source_name', '')} "
                    f"with changed ratio {changed_ratio:.2%}"
                ),
                detected_at=snapshot.get("captured_at", ""),
                importance_score=60,
                url=snapshot.get("page_url"),
                before_value=_truncate(before_text),
                after_value=_truncate(after_text),
                changed_ratio=changed_ratio,
                metadata={"page_url": snapshot.get("page_url")},
            )
        )

    return changes


def _is_blocked_page_snapshot(snapshot: dict) -> bool:
    source_name = str(snapshot.get("source_name", ""))
    page_url = str(snapshot.get("page_url", "")).lower()
    if any(hint in source_name for hint in BLOCKED_SOURCE_NAME_HINTS):
        return True
    if any(hint in page_url for hint in BLOCKED_URL_HINTS):
        return True
    return False


def _snapshot_key(snapshot: dict) -> tuple[str, str, str]:
    return (
        snapshot.get("company_name", ""),
        snapshot.get("source_name", ""),
        snapshot.get("page_url", ""),
    )


def _truncate(text: str, limit: int = 500) -> str:
    return text[:limit]
