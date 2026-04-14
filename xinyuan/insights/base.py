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
