from __future__ import annotations

import re
from hashlib import sha256

from processors.base import ProcessedDocument


WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_raw_document(raw_document: dict) -> ProcessedDocument:
    title = raw_document.get("title", "").strip()
    content_text = raw_document.get("content_text", "")
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
