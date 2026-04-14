from __future__ import annotations

from detectors.base import ChangeRecord


def detect_new_events(
    current_batch_date: str,
    current_events: list[dict],
    previous_events: list[dict],
) -> list[ChangeRecord]:
    previous_keys = {
        _event_key(event)
        for event in previous_events
    }
    changes: list[ChangeRecord] = []

    for event in current_events:
        key = _event_key(event)
        if key in previous_keys:
            continue

        company_name = event.get("company_name") or ", ".join(
            event.get("matched_companies", [])
        )
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


def _event_key(event: dict) -> tuple[str, str, str]:
    return (
        event.get("url", ""),
        event.get("title", ""),
        "|".join(sorted(event.get("event_types", []))),
    )
