from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChangeRecord:
    company_name: str
    source_name: str
    change_type: str
    target_type: str
    title: str
    summary: str
    detected_at: str
    importance_score: int = 50
    url: str | None = None
    before_value: str | None = None
    after_value: str | None = None
    changed_ratio: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
