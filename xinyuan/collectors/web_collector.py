from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CollectedItem, SourceConfig


class WebCollector(BaseCollector):
    source_type = "web"
    LIST_LIKE_PARSERS = {"news_page", "news_hub_page", "ir_page", "notice_hub_page"}
    DATE_RE = re.compile(
        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|20\d{2}年\d{1,2}月\d{1,2}日)"
    )
    DATE_ATTR_SELECTORS = (
        "meta[property='article:published_time']",
        "meta[name='publishdate']",
        "meta[name='pubdate']",
        "meta[name='date']",
        "meta[itemprop='datePublished']",
        "time[datetime]",
        "time",
        ".date",
        ".time",
        ".publish",
        ".published",
        ".post-date",
        ".article-date",
        ".news-date",
        ".article-time",
    )
    CONTENT_SELECTORS = (
        "article",
        ".article",
        ".article-content",
        ".news-content",
        ".post-content",
        ".content",
        ".detail",
        "main",
    )
    TITLE_SELECTORS = ("h1", ".title", ".article-title", ".news-title", ".post-title")

    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        session = requests.Session()
        response = session.get(
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
            article_items = self._extract_list_items(source, soup, response.status_code, session)
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
        session: requests.Session,
    ) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        seen: set[tuple[str, str]] = set()
        article_cache: dict[str, dict[str, str | None]] = {}

        for anchor in soup.find_all("a", href=True):
            href = (anchor.get("href") or "").strip()
            link_text = anchor.get_text(" ", strip=True)
            absolute_url = urljoin(source.url, href)
            if not self._is_candidate_link(source.url, href, absolute_url, link_text):
                continue

            dedupe_key = (absolute_url, link_text)
            if dedupe_key in seen:
                continue

            context_text = self._extract_context_text(anchor)
            article_meta = article_cache.get(absolute_url)
            if article_meta is None:
                article_meta = self._fetch_article_metadata(absolute_url, session)
                article_cache[absolute_url] = article_meta

            published_at = (
                self._extract_date(context_text)
                or article_meta.get("published_at")
            )
            resolved_title = article_meta.get("title") or link_text
            resolved_content = article_meta.get("content_text") or context_text

            items.append(
                CollectedItem(
                    company_name=source.company_name,
                    source_name=source.source_name,
                    source_type=source.source_type,
                    url=absolute_url,
                    title=resolved_title,
                    content_text=resolved_content,
                    published_at=published_at,
                    metadata={
                        "parser_type": source.parser_type,
                        "status_code": status_code,
                        "item_kind": "article_link",
                        "source_page_url": source.url,
                        "published_at_source": article_meta.get("published_at_source"),
                    },
                )
            )
            seen.add(dedupe_key)

            if len(items) >= 20:
                break

        return items

    def _is_candidate_link(
        self,
        source_url: str,
        href: str,
        absolute_url: str,
        link_text: str,
    ) -> bool:
        if not href or not link_text:
            return False
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return False

        source_parts = urlparse(source_url)
        absolute_parts = urlparse(absolute_url)
        same_host = absolute_parts.netloc == source_parts.netloc
        same_path = absolute_parts.path == source_parts.path
        if absolute_parts.fragment and same_host and same_path:
            return False
        if absolute_parts.netloc and not same_host:
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
            "beian",
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
        return self._normalize_date(match.group(1))

    def _fetch_article_metadata(
        self,
        article_url: str,
        session: requests.Session,
    ) -> dict[str, str | None]:
        try:
            response = session.get(
                article_url,
                timeout=20,
                headers={"User-Agent": "xinyuan-monitor/0.1"},
            )
            response.raise_for_status()
        except requests.RequestException:
            return {
                "title": None,
                "content_text": None,
                "published_at": None,
                "published_at_source": None,
            }

        soup = BeautifulSoup(response.text, "html.parser")
        title = self._extract_article_title(soup)
        content_text = self._extract_article_content(soup)
        published_at, published_at_source = self._extract_article_published_at(soup)
        return {
            "title": title,
            "content_text": content_text,
            "published_at": published_at,
            "published_at_source": published_at_source,
        }

    def _extract_article_title(self, soup: BeautifulSoup) -> str | None:
        for selector in self.TITLE_SELECTORS:
            node = soup.select_one(selector)
            if node:
                text = node.get_text(" ", strip=True)
                if text:
                    return text
        if soup.title:
            text = soup.title.get_text(" ", strip=True)
            if text:
                return text
        return None

    def _extract_article_content(self, soup: BeautifulSoup) -> str | None:
        for selector in self.CONTENT_SELECTORS:
            node = soup.select_one(selector)
            if not node:
                continue
            text = node.get_text(" ", strip=True)
            if text and len(text) >= 40:
                return text[:2000]
        body_text = soup.get_text(" ", strip=True)
        return body_text[:2000] if body_text else None

    def _extract_article_published_at(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        for selector in self.DATE_ATTR_SELECTORS:
            for node in soup.select(selector):
                candidate = (
                    node.get("content")
                    or node.get("datetime")
                    or node.get_text(" ", strip=True)
                )
                published_at = self._extract_date(candidate or "")
                if published_at:
                    return published_at, selector

        full_text = soup.get_text(" ", strip=True)
        published_at = self._extract_date(full_text)
        if published_at:
            return published_at, "full_text"

        return None, None

    def _normalize_date(self, value: str) -> str | None:
        if not value:
            return None
        text = value.strip()
        text = text.replace("年", "-").replace("月", "-").replace("日", "")
        text = text.replace("/", "-").replace(".", "-")
        parts = [part for part in text.split("-") if part]
        if len(parts) != 3:
            return None
        try:
            normalized = date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
        return normalized.isoformat()
