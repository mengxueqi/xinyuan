from __future__ import annotations


def build_reason(change: dict, score_reasons: list[str]) -> str:
    if score_reasons:
        return "；".join(score_reasons)

    change_type = change.get("change_type", "")
    if change_type == "new_event":
        return "这是新增事件，值得进入后续人工审阅。"
    if change_type == "page_change":
        return "这是页面内容变化，可能意味着公司对外信息发生更新。"
    if change_type == "job_change":
        return "这是招聘变化，可能反映组织和岗位布局调整。"
    return "建议进一步人工审阅。"
