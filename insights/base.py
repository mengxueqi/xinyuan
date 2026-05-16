from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class InsightRecord:
    company_name: str
    source_name: str
    change_type: str
    target_type: str
    title: str
    summary: str
    importance_score: int
    reason: str
    detected_at: str
    priority_label: str
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessedEventRecord:
    batch_date: str
    company_name: str
    source_name: str
    source_type: str
    url: str
    title: str
    content_text: str
    summary: str
    reason: str
    importance_score: int
    priority_label: str
    published_at: str | None
    fetched_at: str | None
    is_historically_new: bool = False
    linked_change_type: str | None = None
    event_types: list[str] = field(default_factory=list)
    tech_signals: list[str] = field(default_factory=list)
    matched_companies: list[str] = field(default_factory=list)
    matched_focus_keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
