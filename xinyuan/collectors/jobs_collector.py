from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CollectedItem, SourceConfig


JOB_HINTS = (
    "job",
    "jobs",
    "career",
    "careers",
    "position",
    "opening",
    "招聘",
    "职位",
    "岗位",
)


class JobsCollector(BaseCollector):
    source_type = "jobs"

    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        response = requests.get(
            source.url,
            timeout=30,
            headers={"User-Agent": "xinyuan-monitor/0.1"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        text_nodes = []
        for tag in soup.find_all(["a", "li", "h1", "h2", "h3", "h4", "p", "span"]):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue
            lowered = text.lower()
            if any(hint in lowered for hint in JOB_HINTS):
                text_nodes.append(text)

        if not text_nodes:
            text_nodes.append(soup.get_text(separator=" ", strip=True)[:2000])

        return [
            CollectedItem(
                company_name=source.company_name,
                source_name=source.source_name,
                source_type=source.source_type,
                url=source.url,
                title=f"{source.company_name} jobs snapshot",
                content_text="\n".join(text_nodes),
                metadata={
                    "parser_type": source.parser_type,
                    "status_code": response.status_code,
                    "job_signal_count": len(text_nodes),
                },
            )
        ]
