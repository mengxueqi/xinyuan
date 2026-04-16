from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime


def parse_iso_date(value) -> date | None:
    if not value:
        return None
    text = str(value).strip().replace(".", "-").replace("/", "-")
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_iso_datetime(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def is_recent_focus_event(
    event: dict,
    reference_date: date | None,
    max_age_days: int,
) -> bool:
    published_at = parse_iso_date(event.get("published_at"))
    if not published_at:
        return False
    anchor_date = reference_date or parse_iso_date(event.get("batch_date")) or date.today()
    return 0 <= (anchor_date - published_at).days <= max_age_days


def select_focus_events(
    events: list[dict],
    focus_event_types: set[str],
    *,
    reference_date: date | None = None,
    max_items: int = 20,
    max_per_company: int = 6,
    max_age_days: int = 7,
) -> list[dict]:
    filtered = []
    for event in events:
        event_types = set(event.get("event_types_json") or event.get("event_types") or [])
        if not (event_types & focus_event_types):
            continue
        if not is_recent_focus_event(event, reference_date, max_age_days):
            continue
        filtered.append(event)

    deduped = _dedupe_events(filtered)
    deduped.sort(key=_event_sort_key, reverse=True)

    selected: list[dict] = []
    company_counts: dict[str, int] = defaultdict(int)
    used_company_types: set[tuple[str, str]] = set()
    used_global_types: set[str] = set()

    for require_new_global_type, require_new_company_type in (
        (True, True),
        (False, True),
        (False, False),
    ):
        for event in deduped:
            if len(selected) >= max_items:
                return selected
            event_key = _event_identity(event)
            if any(_event_identity(item) == event_key for item in selected):
                continue
            company_name = str(event.get("company_name") or "Unknown")
            if company_counts[company_name] >= max_per_company:
                continue

            event_types = set(event.get("event_types_json") or event.get("event_types") or [])
            focus_types = sorted(event_types & focus_event_types)
            if not focus_types:
                continue

            has_new_global_type = any(item not in used_global_types for item in focus_types)
            has_new_company_type = any((company_name, item) not in used_company_types for item in focus_types)

            if require_new_global_type and not has_new_global_type:
                continue
            if require_new_company_type and not has_new_company_type:
                continue

            selected.append(event)
            company_counts[company_name] += 1
            for item in focus_types:
                used_global_types.add(item)
                used_company_types.add((company_name, item))

    return selected[:max_items]


def _dedupe_events(events: list[dict]) -> list[dict]:
    latest_by_key: dict[tuple[str, str, str], dict] = {}
    for event in events:
        identity = _event_identity(event)
        current = latest_by_key.get(identity)
        if current is None or _event_sort_key(event) > _event_sort_key(current):
            latest_by_key[identity] = event
    return list(latest_by_key.values())


def _event_identity(event: dict) -> tuple[str, str, str]:
    return (
        str(event.get("company_name") or ""),
        str(event.get("url") or ""),
        str(event.get("title") or ""),
    )


def _event_sort_key(event: dict) -> tuple:
    fetched_at = parse_iso_datetime(event.get("fetched_at")) or datetime.min
    batch_date = parse_iso_datetime(event.get("batch_date")) or datetime.min
    published_at = parse_iso_date(event.get("published_at")) or date.min
    return (published_at, fetched_at, batch_date, str(event.get("title") or ""))
