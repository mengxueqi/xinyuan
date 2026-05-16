from __future__ import annotations

from datetime import date

from detectors.base import ChangeRecord


MAX_EVENT_AGE_DAYS = 60
INVALID_EVENT_TITLES = {
    "读取中,请稍候",
    "读取中，请稍候",
    "您的位置：",
    "沪深京A股公告",
}
BLOCKED_SOURCE_NAME_HINTS = ("公司公告页（股票）", "股票页", "财务摘要页")
BLOCKED_URL_HINTS = ("sina.com.cn",)
PRODUCT_SOURCE_NAME_HINTS = ("产品页", "平台页", "解决方案页", "产品中心页", "业务与产品页")


def detect_new_events(
    current_batch_date: str,
    current_events: list[dict],
    historical_events: list[dict],
    historical_known_sources: set[tuple[str, str]] | None = None,
) -> list[ChangeRecord]:
    historical_known_sources = historical_known_sources or set()
    historical_keys = {_event_key(event) for event in historical_events}
    changes: list[ChangeRecord] = []

    for event in current_events:
        key = _event_key(event)
        if key in historical_keys:
            continue
        if _is_invalid_event_title(event.get("title")):
            continue
        if not _is_change_eligible_source(event):
            continue
        if _is_stale_event(event, current_batch_date):
            continue
        if not _has_publish_date(event):
            continue

        company_name = event.get("company_name") or ", ".join(event.get("matched_companies", []))
        source_key = (company_name or "Unknown", event.get("source_name", ""))
        if historical_known_sources and source_key not in historical_known_sources:
            continue

        changes.append(
            ChangeRecord(
                company_name=company_name or "Unknown",
                source_name=event.get("source_name", ""),
                change_type="new_event",
                target_type="event",
                title=event.get("title", "(untitled event)"),
                summary=_build_new_event_summary(company_name or "Unknown", event),
                detected_at=event.get("fetched_at") or current_batch_date,
                importance_score=70 if event.get("event_types") else 50,
                url=event.get("url"),
                metadata={
                    "event_types": event.get("event_types", []),
                    "tech_signals": event.get("tech_signals", []),
                    "matched_companies": event.get("matched_companies", []),
                    "published_at": event.get("published_at"),
                },
            )
        )

    return changes


def _build_new_event_summary(company_name: str, event: dict) -> str:
    event_types = [item for item in event.get("event_types", []) if item]
    if event_types:
        return f"{company_name} 出现新的{', '.join(event_types)}事件"
    return f"{company_name} 出现新的动态事件"


def _has_publish_date(event: dict) -> bool:
    return _parse_date(event.get("published_at")) is not None


def _is_stale_event(event: dict, current_batch_date: str) -> bool:
    published_at = _parse_date(event.get("published_at"))
    batch_date = _parse_date(current_batch_date)
    if not published_at or not batch_date:
        return False
    return (batch_date - published_at).days > MAX_EVENT_AGE_DAYS


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip().replace(".", "-").replace("/", "-")
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _is_invalid_event_title(value: str | None) -> bool:
    if not value:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text in INVALID_EVENT_TITLES or text.startswith("您的位置")


def _is_change_eligible_source(event: dict) -> bool:
    source_name = str(event.get("source_name") or "")
    url = str(event.get("url") or "").lower()
    if any(hint in source_name for hint in BLOCKED_SOURCE_NAME_HINTS):
        return False
    if any(hint in source_name for hint in PRODUCT_SOURCE_NAME_HINTS):
        return False
    if any(hint in url for hint in BLOCKED_URL_HINTS):
        return False
    return True


def _event_key(event: dict) -> tuple[str, str, str]:
    return (
        event.get("url", ""),
        event.get("title", ""),
        "|".join(sorted(event.get("event_types", []))),
    )
