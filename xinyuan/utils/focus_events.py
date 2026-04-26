from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime


INVALID_FOCUS_TITLES = {
    "读取中,请稍候",
    "读取中，请稍候",
    "您的位置：",
    "沪深京A股公告",
}
INVALID_TITLE_PREFIXES = ("您的位置",)
SINA_HOST_HINT = "sina.com.cn"
PRODUCT_SOURCE_NAME_HINTS = ("产品页", "平台页", "解决方案页", "产品中心页", "业务与产品页")
FOCUS_TYPE_WEIGHTS = {
    "product": 20,
    "financing": 20,
    "capacity": 20,
    "ip": 20,
    "performance": 20,
}


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
    event_date = (
        parse_iso_date(event.get("published_at"))
        or parse_iso_date(event.get("detected_at"))
        or parse_iso_date(event.get("batch_date"))
    )
    if not event_date:
        return False
    anchor_date = reference_date or parse_iso_date(event.get("batch_date")) or date.today()
    return 0 <= (anchor_date - event_date).days <= max_age_days


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
        if _is_invalid_focus_title(event.get("title")):
            continue
        if not _is_focus_source_allowed(event):
            continue

        event_types = _extract_event_types(event)
        if not (event_types & focus_event_types):
            continue
        if not is_recent_focus_event(event, reference_date, max_age_days):
            continue

        filtered.append(event)

    deduped = _dedupe_events(filtered)
    deduped.sort(
        key=lambda event: _focus_sort_key(
            event,
            focus_event_types=focus_event_types,
            reference_date=reference_date,
            max_age_days=max_age_days,
        ),
        reverse=True,
    )

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

            event_types = _extract_event_types(event)
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
    detected_at = parse_iso_datetime(event.get("detected_at")) or datetime.min
    batch_date = parse_iso_datetime(event.get("batch_date")) or datetime.min
    published_at = parse_iso_date(event.get("published_at")) or date.min
    source_score = _source_preference_score(event)
    return (
        source_score,
        published_at,
        detected_at,
        fetched_at,
        batch_date,
        str(event.get("title") or ""),
    )


def _focus_sort_key(
    event: dict,
    *,
    focus_event_types: set[str],
    reference_date: date | None,
    max_age_days: int,
) -> tuple:
    event_date = (
        parse_iso_date(event.get("published_at"))
        or parse_iso_date(event.get("detected_at"))
        or parse_iso_date(event.get("batch_date"))
        or date.min
    )
    focus_score = _focus_score(
        event,
        focus_event_types=focus_event_types,
        reference_date=reference_date,
        max_age_days=max_age_days,
    )
    return (event_date, focus_score, *_event_sort_key(event))


def _focus_score(
    event: dict,
    *,
    focus_event_types: set[str],
    reference_date: date | None,
    max_age_days: int,
) -> int:
    focus_types = _extract_event_types(event) & focus_event_types
    score = sum(FOCUS_TYPE_WEIGHTS.get(item, 10) for item in focus_types)
    score += _source_preference_score(event) * 10
    try:
        score += int(event.get("importance_score") or 0)
    except (TypeError, ValueError):
        pass

    event_date = (
        parse_iso_date(event.get("published_at"))
        or parse_iso_date(event.get("detected_at"))
        or parse_iso_date(event.get("batch_date"))
    )
    anchor_date = reference_date or parse_iso_date(event.get("batch_date")) or date.today()
    if event_date:
        age_days = max(0, (anchor_date - event_date).days)
        score += max(0, max_age_days - age_days)

    return score


def _extract_event_types(event: dict) -> set[str]:
    direct = event.get("event_types_json") or event.get("event_types") or []
    if direct:
        return set(direct)
    metadata = event.get("metadata_json") or event.get("metadata") or {}
    if isinstance(metadata, dict):
        return set(metadata.get("event_types", []))
    return set()


def _source_preference_score(event: dict) -> int:
    source_name = str(event.get("source_name") or "")
    url = str(event.get("url") or "").lower()
    if "东方财富公告页" in source_name or "eastmoney" in url:
        return 3
    if "东方财富" in source_name:
        return 2
    if "news" in source_name.lower() or "新闻" in source_name:
        return 1
    return 0


def _is_invalid_focus_title(value: str | None) -> bool:
    if not value:
        return True
    text = str(value).strip()
    if not text:
        return True
    if text in INVALID_FOCUS_TITLES:
        return True
    return any(text.startswith(prefix) for prefix in INVALID_TITLE_PREFIXES)


def _is_focus_source_allowed(event: dict) -> bool:
    source_name = str(event.get("source_name") or "")
    url = str(event.get("url") or "").lower()
    title = str(event.get("title") or "")

    if url.startswith("http://vip.stock.finance.sina.com.cn") or SINA_HOST_HINT in url:
        return False
    if source_name in {"股票页", "财务摘要页"}:
        return False
    if "公司公告页（股票）" in source_name:
        return False
    if any(hint in source_name for hint in PRODUCT_SOURCE_NAME_HINTS):
        return False
    if title in {"沪深京A股公告", "重大事项提醒与新闻公告_投资提醒"}:
        return False
    return True
