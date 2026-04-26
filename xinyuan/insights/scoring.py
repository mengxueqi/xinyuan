from __future__ import annotations

from datetime import date


HIGH_SIGNAL_KEYWORDS = {
    "financing",
    "funding",
    "bond",
    "capacity",
    "expansion",
    "project",
    "partnership",
    "collaboration",
    "pilot plant",
    "manufacturing",
    "product",
    "ip",
    "patent",
    "performance",
    "earnings",
    "annual report",
    "forecast",
    "environment",
    "environmental impact",
    "construction",
    "融资",
    "扩产",
    "产能",
    "项目",
    "合作",
    "新产品",
    "知识产权",
    "专利",
    "业绩",
    "业绩快报",
    "业绩预告",
    "年度报告",
    "环评",
    "环保",
    "建设",
    "中试",
}

MID_HIGH_EVENT_KEYWORDS = {
    "融资",
    "扩产",
    "产能",
    "项目",
    "合作",
    "bond",
    "financing",
    "capacity",
    "expansion",
    "project",
    "partnership",
    "collaboration",
}

MID_EVENT_KEYWORDS = {
    "年报",
    "年度报告",
    "半年报",
    "一季报",
    "三季报",
    "业绩",
    "业绩快报",
    "业绩预告",
    "业绩说明会",
    "annual report",
    "interim report",
    "earnings",
    "earnings forecast",
}

ENVIRONMENT_PROJECT_KEYWORDS = {
    "环保",
    "环评",
    "环境",
    "项目建设",
    "建设",
    "construction",
    "environment",
    "environmental impact",
}

SOURCE_NAME_SCORES = {
    "东方财富公告页": 15,
    "东方财富股票页": 8,
    "东方财富财务分析页": 6,
    "公司公告页": 10,
    "新闻中心页": 12,
    "新闻动态页": 12,
    "官方新闻页": 12,
    "新闻资讯页": 12,
    "新闻与活动页": 12,
    "投资者关系页": 8,
    "招聘页": 4,
}

SOURCE_TYPE_SCORES = {
    "rss": 10,
    "web": 6,
    "jobs": 2,
}


def priority_from_score(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def score_event(
    event: dict,
    *,
    is_historically_new: bool = False,
    linked_change: dict | None = None,
) -> tuple[int, list[str]]:
    score = 40
    reasons: list[str] = []

    source_name = str(event.get("source_name") or "")
    source_type = str(event.get("source_type") or "")
    title = str(event.get("title") or "")
    content_text = str(event.get("content_text") or "")
    event_types = list(event.get("event_types") or event.get("event_types_json") or [])
    tech_signals = list(event.get("tech_signals") or event.get("tech_signals_json") or [])
    focus_keywords = list(
        event.get("matched_focus_keywords")
        or event.get("matched_focus_keywords_json")
        or []
    )

    text_blob = " ".join(
        [
            title,
            content_text,
            " ".join(event_types),
            " ".join(tech_signals),
            " ".join(focus_keywords),
        ]
    ).lower()

    if is_historically_new:
        score += 15
        reasons.append("Historically new event in the event library.")

    source_score = SOURCE_NAME_SCORES.get(source_name, SOURCE_TYPE_SCORES.get(source_type, 0))
    if source_score:
        score += source_score
        reasons.append(f"Source confidence bonus from {source_name or source_type}.")

    matched_high_signals = sorted(
        keyword for keyword in HIGH_SIGNAL_KEYWORDS if keyword.lower() in text_blob
    )
    if matched_high_signals:
        score += min(25, 5 * len(matched_high_signals))
        reasons.append(
            "Matched high-value signals: "
            + ", ".join(matched_high_signals[:5])
        )

    matched_mid_high = sorted(
        keyword for keyword in MID_HIGH_EVENT_KEYWORDS if keyword.lower() in text_blob
    )
    matched_mid = sorted(
        keyword for keyword in MID_EVENT_KEYWORDS if keyword.lower() in text_blob
    )
    matched_environment = sorted(
        keyword for keyword in ENVIRONMENT_PROJECT_KEYWORDS if keyword.lower() in text_blob
    )

    if matched_mid_high:
        score = max(score, 70)
        reasons.append(
            "Matched financing/capacity/project/partnership level signals: "
            + ", ".join(matched_mid_high[:4])
        )
    elif matched_mid:
        score = max(score, 62)
        reasons.append(
            "Matched performance/reporting level signals: "
            + ", ".join(matched_mid[:4])
        )

    if matched_environment:
        score = max(score, 62)
        reasons.append(
            "Matched environment or project-construction signals: "
            + ", ".join(matched_environment[:4])
        )

    age_bonus = _recency_bonus(event.get("published_at"))
    if age_bonus:
        score += age_bonus
        reasons.append("Recent publication date bonus.")

    if linked_change and linked_change.get("change_type") in {"page_change", "job_change"}:
        score += 5
        reasons.append("Linked to another meaningful detected change in the same batch.")

    score = max(0, min(100, score))
    return score, reasons


def score_change(change: dict) -> tuple[int, list[str]]:
    score = 40
    reasons: list[str] = []
    change_type = change.get("change_type", "")

    if change_type == "new_event":
        metadata = change.get("metadata", {})
        event_payload = {
            "source_name": change.get("source_name"),
            "source_type": "web",
            "title": change.get("title"),
            "content_text": change.get("summary", ""),
            "event_types": metadata.get("event_types", []),
            "tech_signals": metadata.get("tech_signals", []),
            "matched_focus_keywords": metadata.get("matched_focus_keywords", []),
            "published_at": metadata.get("published_at"),
        }
        return score_event(event_payload, is_historically_new=True)

    if change_type == "job_change":
        score += 10
        reasons.append("Job page changed, which can indicate hiring or team expansion.")
    elif change_type == "page_change":
        score += 8
        reasons.append("Page content changed in a meaningful way.")

    source_name = str(change.get("source_name") or "")
    source_score = SOURCE_NAME_SCORES.get(source_name, 0)
    if source_score:
        score += min(source_score, 12)
        reasons.append(f"Source confidence bonus from {source_name}.")

    text_blob = " ".join(
        [
            str(change.get("title") or ""),
            str(change.get("summary") or ""),
            str(change.get("before_value") or ""),
            str(change.get("after_value") or ""),
            " ".join(change.get("metadata", {}).get("event_types", [])),
            " ".join(change.get("metadata", {}).get("tech_signals", [])),
        ]
    ).lower()

    matched_high_signals = sorted(
        keyword for keyword in HIGH_SIGNAL_KEYWORDS if keyword.lower() in text_blob
    )
    if matched_high_signals:
        score += min(20, 4 * len(matched_high_signals))
        reasons.append(
            "Matched high-value change signals: "
            + ", ".join(matched_high_signals[:5])
        )

    changed_ratio = change.get("changed_ratio")
    if isinstance(changed_ratio, (int, float)):
        if changed_ratio >= 0.15:
            score += 12
            reasons.append("Large change ratio detected.")
        elif changed_ratio >= 0.05:
            score += 5
            reasons.append("Moderate change ratio detected.")

    score = max(0, min(100, score))
    return score, reasons


def _recency_bonus(value: str | None) -> int:
    parsed_date = _parse_date(value)
    if not parsed_date:
        return 0
    age_days = max(0, (date.today() - parsed_date).days)
    if age_days <= 7:
        return 10
    if age_days <= 30:
        return 6
    if age_days <= 60:
        return 3
    return 0


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
