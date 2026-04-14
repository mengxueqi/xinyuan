from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CollectedItem, SourceConfig


class WebCollector(BaseCollector):
    source_type = "web"
    LIST_LIKE_PARSERS = {"news_page", "news_hub_page", "ir_page", "notice_hub_page"}
    DATE_RE = re.compile(
        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"
    )

    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        response = requests.get(
            source.url,
            timeout=30,
            headers={"User-Agent": "xinyuan-monitor/0.1"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else source.source_name
        content_text = soup.get_text(separator=" ", strip=True)
        parser_type = (source.parser_type or "").lower()

        page_snapshot = CollectedItem(
            company_name=source.company_name,
            source_name=source.source_name,
            source_type=source.source_type,
            url=source.url,
            title=title,
            content_text=content_text,
            metadata={
                "parser_type": source.parser_type,
                "status_code": response.status_code,
                "item_kind": "page_snapshot",
            },
        )

        if parser_type in self.LIST_LIKE_PARSERS:
            article_items = self._extract_list_items(source, soup, response.status_code)
            if article_items:
                return article_items + [page_snapshot]

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
                    "item_kind": "page_snapshot",
                },
            )
        ]

    def _extract_list_items(
        self,
        source: SourceConfig,
        soup: BeautifulSoup,
        status_code: int,
    ) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        seen: set[tuple[str, str]] = set()

        for anchor in soup.find_all("a", href=True):
            href = (anchor.get("href") or "").strip()
            link_text = anchor.get_text(" ", strip=True)
            if not self._is_candidate_link(href, link_text):
                continue

            absolute_url = urljoin(source.url, href)
            dedupe_key = (absolute_url, link_text)
            if dedupe_key in seen:
                continue

            context_text = self._extract_context_text(anchor)
            published_at = self._extract_date(context_text)

            items.append(
                CollectedItem(
                    company_name=source.company_name,
                    source_name=source.source_name,
                    source_type=source.source_type,
                    url=absolute_url,
                    title=link_text,
                    content_text=context_text,
                    published_at=published_at,
                    metadata={
                        "parser_type": source.parser_type,
                        "status_code": status_code,
                        "item_kind": "article_link",
                        "source_page_url": source.url,
                    },
                )
            )
            seen.add(dedupe_key)

            if len(items) >= 20:
                break

        return items

    def _is_candidate_link(self, href: str, link_text: str) -> bool:
        if not href or not link_text:
            return False
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return False

        lowered_href = href.lower()
        lowered_text = link_text.lower()
        nav_hints = (
            "privacy",
            "terms",
            "login",
            "register",
            "contact",
            "about",
            "careers",
            "join us",
            "home",
        )
        if any(hint in lowered_href for hint in nav_hints):
            return False
        if any(hint in lowered_text for hint in nav_hints):
            return False

        if len(link_text) < 8:
            return False

        dense_tokens = [token for token in re.split(r"\s+", link_text) if token]
        if len(dense_tokens) > 20:
            return False

        return True

    def _extract_context_text(self, anchor) -> str:
        parent = anchor.parent
        if parent is None:
            return anchor.get_text(" ", strip=True)

        context_text = parent.get_text(" ", strip=True)
        if len(context_text) < len(anchor.get_text(" ", strip=True)) + 8 and parent.parent is not None:
            context_text = parent.parent.get_text(" ", strip=True)

        if len(context_text) > 500:
            context_text = context_text[:500]
        return context_text or anchor.get_text(" ", strip=True)

    def _extract_date(self, text: str) -> str | None:
        match = self.DATE_RE.search(text or "")
        if not match:
            return None
        return match.group(1)
