from __future__ import annotations

import json
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from collectors.base import BaseCollector, CollectedItem, SourceConfig


class WebCollector(BaseCollector):
    source_type = "web"
    LIST_LIKE_PARSERS = {"news_page", "news_hub_page", "ir_page", "notice_hub_page"}
    INVALID_TITLE_PATTERNS = ("读取中,请稍候", "读取中，请稍候", "您的位置：", "loading")
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
    EASTMONEY_NOTICE_RE = re.compile(r"/notices/stock/(?P<code>\d{6})\.html", re.I)

    def collect(self, source: SourceConfig) -> list[CollectedItem]:
        session = requests.Session()
        response = session.get(
            source.url,
            timeout=30,
            headers={"User-Agent": "xinyuan-monitor/0.1"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = self._clean_title(soup.title.get_text(strip=True) if soup.title else "") or source.source_name
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

        eastmoney_items = self._collect_eastmoney_notice_items(source, session)
        if eastmoney_items:
            return eastmoney_items + [page_snapshot]

        if parser_type in self.LIST_LIKE_PARSERS:
            article_items = self._extract_list_items(source, soup, response.status_code, session)
            if article_items:
                return article_items + [page_snapshot]

        return [page_snapshot]

    def _collect_eastmoney_notice_items(
        self,
        source: SourceConfig,
        session: requests.Session,
    ) -> list[CollectedItem]:
        match = self.EASTMONEY_NOTICE_RE.search(source.url)
        if not match:
            return []

        stock_code = match.group("code")
        api_url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        response = session.get(
            api_url,
            params={
                "ann_type": "A",
                "client_source": "web",
                "stock_list": stock_code,
                "page_index": 1,
                "page_size": 20,
                "cb": "callback",
            },
            timeout=30,
            headers={"User-Agent": "xinyuan-monitor/0.1"},
        )
        response.raise_for_status()

        payload = self._parse_jsonp_payload(response.text)
        notices = payload.get("data", {}).get("list", []) if isinstance(payload, dict) else []

        items: list[CollectedItem] = []
        for notice in notices:
            art_code = str(notice.get("art_code") or "").strip()
            title = self._clean_title(notice.get("title_ch") or notice.get("title") or "")
            if not art_code or not title:
                continue

            columns = [item.get("column_name", "") for item in notice.get("columns", []) if item.get("column_name")]
            notice_date = self._normalize_date(str(notice.get("notice_date") or ""))
            detail_url = f"https://data.eastmoney.com/notices/detail/{stock_code}/{art_code}.html"
            content_parts = [title]
            if columns:
                content_parts.append(" / ".join(columns))

            items.append(
                CollectedItem(
                    company_name=source.company_name,
                    source_name=source.source_name,
                    source_type=source.source_type,
                    url=detail_url,
                    title=title,
                    content_text=" ".join(part for part in content_parts if part),
                    published_at=notice_date,
                    metadata={
                        "parser_type": source.parser_type,
                        "status_code": response.status_code,
                        "item_kind": "article_link",
                        "source_page_url": source.url,
                        "published_at_source": "eastmoney_notice_api",
                        "notice_columns": columns,
                        "art_code": art_code,
                    },
                )
            )

        return items

    def _parse_jsonp_payload(self, text: str) -> dict:
        stripped = text.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
        start = stripped.find("(")
        end = stripped.rfind(")")
        if start == -1 or end == -1 or end <= start:
            return {}
        return json.loads(stripped[start + 1 : end])

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

            published_at = self._extract_date(context_text) or article_meta.get("published_at")
            resolved_title = self._pick_best_title(
                article_meta.get("title"),
                link_text,
                absolute_url,
            ) or source.source_name
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

        if len(link_text) < 4:
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
                cleaned = self._clean_title(node.get_text(" ", strip=True))
                if cleaned:
                    return cleaned
        if soup.title:
            cleaned = self._clean_title(soup.title.get_text(" ", strip=True))
            if cleaned:
                return cleaned
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
            node = soup.select_one(selector)
            if not node:
                continue
            candidate = node.get("content") or node.get("datetime") or node.get_text(" ", strip=True)
            normalized = self._normalize_date(candidate)
            if normalized:
                return normalized, selector

        text = soup.get_text(" ", strip=True)
        normalized = self._extract_date(text)
        if normalized:
            return normalized, "text"
        return None, None

    def _pick_best_title(
        self,
        article_title: str | None,
        link_text: str | None,
        article_url: str,
    ) -> str | None:
        for candidate in (article_title, link_text):
            cleaned = self._clean_title(candidate)
            if cleaned:
                return cleaned
        parsed = urlparse(article_url)
        slug = parsed.path.rstrip("/").split("/")[-1]
        return slug or None

    def _clean_title(self, value: str | None) -> str | None:
        if not value:
            return None

        text = re.sub(r"\s+", " ", value).strip()
        if not text or self._is_invalid_title(text):
            return None

        if text.startswith("您的位置："):
            remainder = text.replace("您的位置：", "", 1).strip(" >|-_")
            text = remainder or text

        text = re.sub(r"[_\-\|\s]*(新浪财经|新浪网|东方财富网|数据中心)$", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^\S+\(\d{6}\)\s*[:：_-]\s*", "", text).strip()
        text = re.sub(r"^[^:：]{1,20}\s*_\s*", "", text).strip()

        if not text or self._is_invalid_title(text):
            return None
        return text.strip(" -_|") or None

    def _is_invalid_title(self, value: str | None) -> bool:
        if not value:
            return True
        lowered = value.strip().lower()
        if not lowered:
            return True
        return any(pattern.lower() in lowered for pattern in self.INVALID_TITLE_PATTERNS)

    def _normalize_date(self, value: str | None) -> str | None:
        if not value:
            return None

        text = str(value).strip()
        if not text:
            return None

        match = self.DATE_RE.search(text)
        if not match:
            return None

        raw = (
            match.group(1)
            .replace("年", "-")
            .replace("月", "-")
            .replace("日", "")
            .replace("/", "-")
            .replace(".", "-")
        )
        parts = [part for part in raw.split("-") if part]
        if len(parts) != 3:
            return None
        year, month, day = (int(part) for part in parts)
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
