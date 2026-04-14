from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CollectedItem, SourceConfig


class WebCollector(BaseCollector):
    source_type = "web"

    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        response = requests.get(
            source.url,
            timeout=30,
            headers={"User-Agent": "xinyuan-monitor/0.1"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else source.source_name

        # Keep the first version simple: one page in, one normalized document out.
        content_text = soup.get_text(separator=" ", strip=True)

        return [
            CollectedItem(
                company_name=source.company_name,
                source_name=source.source_name,
                source_type=source.source_type,
                url=source.url,
                title=title,
                content_text=content_text,
                metadata={
                    "parser_type": source.parser_type,
                    "status_code": response.status_code,
                },
            )
        ]
