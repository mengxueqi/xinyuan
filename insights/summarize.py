from __future__ import annotations


def summarize_event(event: dict, *, is_historically_new: bool = False) -> str:
    company_name = event.get("company_name", "Unknown company")
    source_name = event.get("source_name", "source")
    title = event.get("title", "(untitled event)")
    event_types = event.get("event_types") or event.get("event_types_json") or []
    event_text = ", ".join(event_types) if event_types else "uncategorized"

    if is_historically_new:
        return f"{company_name} 出现新的{event_text}事件：{title}"
    return f"{company_name} 在{source_name}新增事件记录：{title}"


def summarize_change(change: dict) -> str:
    company_name = change.get("company_name", "Unknown company")
    source_name = change.get("source_name", "source")
    change_type = change.get("change_type", "")
    title = change.get("title", "(untitled change)")
    metadata = change.get("metadata", {})

    if change_type == "new_event":
        event_types = metadata.get("event_types", [])
        event_text = ", ".join(event_types) if event_types else "动态"
        return f"{company_name} 出现新的{event_text}事件：{title}"

    if change_type == "page_change":
        return f"{company_name} 的{source_name}页面发生更新：{title}"

    if change_type == "job_change":
        return f"{company_name} 的{source_name}招聘页面发生更新：{title}"

    return f"{company_name} 在{source_name}检测到变化：{title}"
