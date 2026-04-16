from __future__ import annotations

from datetime import date

from detectors.base import ChangeRecord


MAX_EVENT_AGE_DAYS = 7


def detect_new_events(
    current_batch_date: str,
    current_events: list[dict],
    previous_events: list[dict],
    previous_known_sources: set[tuple[str, str]] | None = None,
) -> list[ChangeRecord]:
    previous_known_sources = previous_known_sources or set()
    previous_keys = {
        _event_key(event)
        for event in previous_events
    }
    changes: list[ChangeRecord] = []

    for event in current_events:
        key = _event_key(event)
        if key in previous_keys:
            continue
        if _is_stale_event(event, current_batch_date):
            continue

        company_name = event.get("company_name") or ", ".join(
            event.get("matched_companies", [])
        )
        source_key = (
            company_name or "Unknown",
            event.get("source_name", ""),
        )
        if previous_known_sources and source_key not in previous_known_sources:
            continue
        changes.append(
            ChangeRecord(
                company_name=company_name or "Unknown",
                source_name=event.get("source_name", ""),
                change_type="new_event",
                target_type="event",
                title=event.get("title", "(untitled event)"),
                summary=(
                    f"New event detected on {current_batch_date}: "
                    f"{', '.join(event.get('event_types', [])) or 'uncategorized'}"
                ),
                detected_at=event.get("fetched_at") or current_batch_date,
                importance_score=70 if event.get("event_types") else 50,
                url=event.get("url"),
                metadata={
                    "event_types": event.get("event_types", []),
                    "tech_signals": event.get("tech_signals", []),
                    "matched_companies": event.get("matched_companies", []),
                },
            )
        )

    return changes


def _is_stale_event(event: dict, current_batch_date: str) -> bool:
    published_at = _parse_date(event.get("published_at"))
    batch_date = _parse_date(current_batch_date)
    if not published_at or not batch_date:
        return False
    return (batch_date - published_at).days > MAX_EVENT_AGE_DAYS


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _event_key(event: dict) -> tuple[str, str, str]:
    return (
        event.get("url", ""),
        event.get("title", ""),
        "|".join(sorted(event.get("event_types", []))),
    )
