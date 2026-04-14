from __future__ import annotations


HIGH_SIGNAL_KEYWORDS = {
    "产能",
    "工厂",
    "中试",
    "pilot plant",
    "manufacturing",
    "量产",
    "商业化",
    "合作",
    "partnership",
    "融资",
    "ipo",
    "上市",
    "审批",
    "gras",
    "fda",
    "nmpa",
}


def score_change(change: dict) -> tuple[int, list[str]]:
    score = 40
    reasons: list[str] = []

    change_type = change.get("change_type", "")
    text_blob = " ".join(
        [
            change.get("title", ""),
            change.get("summary", ""),
            change.get("before_value", "") or "",
            change.get("after_value", "") or "",
            " ".join(change.get("metadata", {}).get("event_types", [])),
            " ".join(change.get("metadata", {}).get("tech_signals", [])),
        ]
    ).lower()
    source_name = change.get("source_name", "").lower()

    if change_type == "new_event":
        score += 15
        reasons.append("新增事件通常比普通文本变动更值得关注")
    elif change_type == "job_change":
        score += 10
        reasons.append("招聘变化可能反映团队和产能布局调整")
    elif change_type == "page_change":
        score += 8
        reasons.append("官网页面变化可能反映公司对外叙事或能力表述变化")

    if "官网" in source_name or "official" in source_name:
        score += 15
        reasons.append("来源接近官方渠道，可信度较高")
    if "投资者" in source_name or "regulatory" in source_name:
        score += 20
        reasons.append("来源接近公告或监管渠道，重要性较高")
    if "招聘" in source_name or "职位" in source_name:
        score += 8
        reasons.append("来源为招聘页面，可用于观察团队扩张")

    matched_high_signals = sorted(
        keyword for keyword in HIGH_SIGNAL_KEYWORDS if keyword.lower() in text_blob
    )
    if matched_high_signals:
        score += min(25, 5 * len(matched_high_signals))
        reasons.append(
            f"命中高价值信号词：{', '.join(matched_high_signals[:5])}"
        )

    changed_ratio = change.get("changed_ratio")
    if isinstance(changed_ratio, (int, float)):
        if changed_ratio >= 0.15:
            score += 12
            reasons.append("页面变化幅度较明显")
        elif changed_ratio >= 0.05:
            score += 5
            reasons.append("页面变化达到可观察阈值")

    score = max(0, min(100, score))
    return score, reasons
