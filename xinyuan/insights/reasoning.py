from __future__ import annotations


EVENT_REASON_MAP = {
    "financing": "这可能反映公司融资、发债或资本市场动作，通常值得持续跟踪。",
    "capacity": "这可能反映产能、项目建设或制造能力推进，是产业化的重要信号。",
    "performance": "这属于业绩披露或经营表现相关信息，适合结合后续经营动态持续观察。",
    "product": "这可能反映产品布局或商业化推进，对业务进展有参考价值。",
    "ip": "这反映了知识产权或专利相关动作，可能体现技术布局变化。",
    "partnership": "这可能反映外部合作推进，值得关注后续落地情况。",
    "regulatory": "这属于监管或合规相关信息，可能影响项目推进节奏。",
    "recruiting": "这可能反映组织扩张或团队结构调整。",
}


def build_event_reason(event: dict, score_reasons: list[str]) -> str:
    event_types = event.get("event_types") or event.get("event_types_json") or []
    for event_type in event_types:
        if event_type in EVENT_REASON_MAP:
            return EVENT_REASON_MAP[event_type]
    if event_types:
        return "这是一个被结构化识别出来的重要事件，建议结合原文继续判断。"
    return "这是一个新进入监控视野的事件，建议结合原文进一步确认价值。"


def build_reason(change: dict, score_reasons: list[str]) -> str:
    change_type = change.get("change_type", "")
    if change_type == "new_event":
        event_types = change.get("metadata", {}).get("event_types", [])
        for event_type in event_types:
            if event_type in EVENT_REASON_MAP:
                return EVENT_REASON_MAP[event_type]
        return "这是历史事件库中首次出现的事件，建议结合原文确认其业务重要性。"
    if change_type == "page_change":
        return "官网页面出现实质更新，通常意味着公司对外信息口径或业务描述发生调整。"
    if change_type == "job_change":
        return "招聘页面变化通常意味着团队扩张、岗位结构变化或阶段性用人需求调整。"
    return "这是一个值得关注的变化，建议结合原始内容继续判断。"


def build_score_basis(score_reasons: list[str]) -> str:
    if not score_reasons:
        return "基于通用规则完成评分。"
    return "；".join(score_reasons)
