from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class SourceConfig:
    company_name: str
    source_name: str
    source_type: str
    url: str
    parser_type: str = "generic"
    crawl_frequency: str = "daily"
    is_active: bool = True
    priority: str = "medium"
    notes: str = ""


@dataclass(slots=True)
class CollectedItem:
    company_name: str
    source_name: str
    source_type: str
    url: str
    title: str
    content_text: str
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class BaseCollector(ABC):
    source_type: str = "generic"

    @abstractmethod
    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        raise NotImplementedError
