from __future__ import annotations

from processors.base import ProcessedDocument
from processors.entities import KeywordRegistry


EVENT_RULES = {
    "financing": [
        "融资",
        "募资",
        "战略投资",
        "发债",
        "债券",
        "超短期融资券",
        "a轮",
        "b轮",
        "c轮",
        "ipo",
        "上市",
        "financing",
        "funding",
        "bond",
    ],
    "performance": [
        "业绩",
        "业绩快报",
        "业绩预告",
        "业绩说明会",
        "年报",
        "年度报告",
        "年度报告摘要",
        "半年报",
        "半年度报告",
        "一季报",
        "一季度报告",
        "一季度报告正文",
        "三季报",
        "三季度报告",
        "annual report",
        "earnings",
        "results",
        "forecast",
    ],
    "partnership": [
        "合作",
        "战略合作",
        "联合开发",
        "共同开发",
        "签约",
        "伙伴关系",
        "partnership",
        "collaboration",
    ],
    "capacity": [
        "扩产",
        "产能",
        "工厂",
        "项目",
        "建设",
        "投产",
        "试生产",
        "量产",
        "制造",
        "中试",
        "platform",
        "manufacturing",
        "pilot plant",
        "commercialization",
        "scale-up",
    ],
    "product": [
        "产品",
        "新品",
        "新产品",
        "产品发布",
        "product launch",
    ],
    "regulatory": [
        "审批",
        "备案",
        "许可",
        "认证",
        "监管",
        "合规",
        "gras",
        "fda",
        "efsa",
        "nmpa",
    ],
    "recruiting": [
        "招聘",
        "加入我们",
        "careers",
        "jobs",
        "process engineer",
        "fermentation engineer",
        "qa",
    ],
    "ip": [
        "知识产权",
        "专利",
        "patent",
    ],
    "management": [
        "高管",
        "董事",
        "监事",
        "任命",
        "离职",
        "管理层",
    ],
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
