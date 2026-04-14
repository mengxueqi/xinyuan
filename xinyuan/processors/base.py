from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProcessedDocument:
    company_name: str
    source_name: str
    source_type: str
    url: str
    title: str
    normalized_title: str
    content_text: str
    normalized_text: str
    content_hash: str
    published_at: str | None = None
    fetched_at: str | None = None
    matched_companies: list[str] = field(default_factory=list)
    matched_aliases: list[str] = field(default_factory=list)
    matched_focus_keywords: list[str] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    tech_signals: list[str] = field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
