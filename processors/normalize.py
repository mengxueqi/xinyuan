from __future__ import annotations

import re
from hashlib import sha256
from urllib.parse import urlparse

from processors.base import ProcessedDocument


WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def extract_lead_article_title(content_text: str) -> str | None:
    text = normalize_whitespace(content_text)
    if not text:
        return None

    marker_positions = [
        text.find(marker)
        for marker in (
            "\u6765\u6e90\uff1a",
            "\u4f5c\u8005:",
            "\u4f5c\u8005\uff1a",
            "\u65e5\u671f:",
            "\u65e5\u671f\uff1a",
        )
        if text.find(marker) > 0
    ]
    if not marker_positions:
        return None

    candidate = normalize_whitespace(text[: min(marker_positions)]).strip(" -_|")
    if 4 <= len(candidate) <= 120:
        return candidate
    return None


def repair_article_title(raw_document: dict, title: str, content_text: str) -> str:
    metadata = raw_document.get("metadata", {}) or {}
    url_path = urlparse(str(raw_document.get("url") or "")).path.lower()
    if metadata.get("item_kind") != "article_link":
        return title
    if "newsxq.aspx" not in url_path:
        return title

    lead_title = extract_lead_article_title(content_text)
    return lead_title or title


def normalize_raw_document(raw_document: dict) -> ProcessedDocument:
    title = raw_document.get("title", "").strip()
    content_text = raw_document.get("content_text", "")
    title = repair_article_title(raw_document, title, content_text)
    normalized_title = normalize_whitespace(title)
    normalized_text = normalize_whitespace(content_text)
    content_hash = raw_document.get("content_hash") or sha256(
        normalized_text.encode("utf-8")
    ).hexdigest()

    return ProcessedDocument(
        company_name=raw_document.get("company_name", ""),
        source_name=raw_document.get("source_name", ""),
        source_type=raw_document.get("source_type", ""),
        url=raw_document.get("url", ""),
        title=title,
        normalized_title=normalized_title,
        content_text=content_text,
        normalized_text=normalized_text,
        content_hash=content_hash,
        published_at=raw_document.get("published_at"),
        fetched_at=raw_document.get("fetched_at"),
        metadata=raw_document.get("metadata", {}),
    )
