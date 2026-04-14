from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from processors.base import ProcessedDocument


class KeywordRegistry:
    def __init__(self) -> None:
        self.company_aliases: dict[str, list[str]] = defaultdict(list)
        self.company_focus_keywords: dict[str, list[str]] = defaultdict(list)
        self.global_event_keywords: list[str] = []
        self.global_tech_keywords: list[str] = []

    @classmethod
    def from_csv(cls, csv_path: Path) -> "KeywordRegistry":
        registry = cls()
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                scope = row["scope"]
                company_name = row["company_name"]
                keyword = row["keyword"].strip()
                keyword_type = row["keyword_type"]

                if not keyword:
                    continue

                if scope == "company" and keyword_type == "alias":
                    registry.company_aliases[company_name].append(keyword)
                elif scope == "company" and keyword_type == "focus":
                    registry.company_focus_keywords[company_name].append(keyword)
                elif scope == "global" and keyword_type == "event":
                    registry.global_event_keywords.append(keyword)
                elif scope == "global" and keyword_type == "tech":
                    registry.global_tech_keywords.append(keyword)

        return registry

    def match_document(self, document: ProcessedDocument) -> ProcessedDocument:
        text_blob = " ".join(
            [
                document.company_name,
                document.title,
                document.normalized_text,
            ]
        )
        lowered_text = text_blob.lower()

        matched_companies = set()
        matched_aliases = set()
        matched_focus_keywords = set()

        tracked_companies = set(self.company_aliases) | set(self.company_focus_keywords)

        if document.company_name and document.company_name in tracked_companies:
            matched_companies.add(document.company_name)

        for company_name, aliases in self.company_aliases.items():
            for alias in aliases:
                if alias.lower() in lowered_text:
                    matched_companies.add(company_name)
                    matched_aliases.add(alias)

        for company_name in matched_companies:
            for keyword in self.company_focus_keywords.get(company_name, []):
                if keyword.lower() in lowered_text:
                    matched_focus_keywords.add(keyword)

        document.matched_companies = sorted(matched_companies)
        document.matched_aliases = sorted(matched_aliases)
        document.matched_focus_keywords = sorted(matched_focus_keywords)
        return document
