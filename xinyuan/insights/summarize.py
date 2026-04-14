from __future__ import annotations


def summarize_change(change: dict) -> str:
    company_name = change.get("company_name", "该公司")
    source_name = change.get("source_name", "相关页面")
    change_type = change.get("change_type", "")
    title = change.get("title", "")
    metadata = change.get("metadata", {})

    if change_type == "new_event":
        event_types = metadata.get("event_types", [])
        event_text = "、".join(event_types) if event_types else "新增动态"
        return f"{company_name} 出现新的{event_text}事件：{title}"

    if change_type == "page_change":
        return f"{company_name} 的 {source_name} 页面出现内容更新：{title}"

    if change_type == "job_change":
        return f"{company_name} 的 {source_name} 出现招聘内容变化：{title}"

    return f"{company_name} 出现新的变化：{title}"
