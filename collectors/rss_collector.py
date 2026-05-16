from __future__ import annotations

from email.utils import parsedate_to_datetime

import feedparser

from collectors.base import BaseCollector, CollectedItem, SourceConfig


class RSSCollector(BaseCollector):
    source_type = "rss"

    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        feed = feedparser.parse(source.url)
        items: list[CollectedItem] = []

        for entry in feed.entries:
            published_at = None
            if getattr(entry, "published", None):
                try:
                    published_at = parsedate_to_datetime(entry.published).isoformat()
                except (TypeError, ValueError, IndexError):
                    published_at = None

            items.append(
                CollectedItem(
                    company_name=source.company_name,
                    source_name=source.source_name,
                    source_type=source.source_type,
                    url=getattr(entry, "link", source.url),
                    title=getattr(entry, "title", "(untitled rss item)"),
                    content_text=getattr(entry, "summary", ""),
                    published_at=published_at,
                    metadata={
                        "feed_url": source.url,
                        "parser_type": source.parser_type,
                    },
                )
            )

        return items
