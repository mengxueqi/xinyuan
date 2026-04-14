from __future__ import annotations

from processors.base import ProcessedDocument
from processors.entities import KeywordRegistry


EVENT_RULES = {
    "financing": ["融资", "募资", "战略投资", "A轮", "B轮", "C轮", "IPO", "上市"],
    "partnership": [
        "合作",
        "战略合作",
        "联合开发",
        "共同开发",
        "签约",
        "partnership",
        "collaboration",
    ],
    "capacity": [
        "扩产",
        "投产",
        "量产",
        "中试",
        "试生产",
        "产线",
        "产能",
        "工厂",
        "manufacturing",
        "pilot plant",
        "commercialization",
        "商业化",
        "scale-up",
    ],
    "product": ["产品发布", "新品", "product launch"],
    "regulatory": ["审批", "备案", "许可", "认证", "GRAS", "FDA", "EFSA", "NMPA"],
    "recruiting": [
        "招聘",
        "加入我们",
        "careers",
        "jobs",
        "process engineer",
        "fermentation engineer",
        "职位",
        "岗位",
    ],
    "ip": ["专利", "知识产权", "patent"],
    "management": ["任命", "离职", "高管", "董事"],
}


def classify_document(
    document: ProcessedDocument, registry: KeywordRegistry
) -> ProcessedDocument:
    text_blob = " ".join(
        [
            document.title,
            document.normalized_text,
            " ".join(document.matched_focus_keywords),
        ]
    ).lower()

    event_types = []
    for event_type, keywords in EVENT_RULES.items():
        if any(keyword.lower() in text_blob for keyword in keywords):
            event_types.append(event_type)

    tech_signals = [
        keyword
        for keyword in registry.global_tech_keywords
        if keyword.lower() in text_blob
    ]

    document.event_types = sorted(set(event_types))
    document.tech_signals = sorted(set(tech_signals))
    return document
