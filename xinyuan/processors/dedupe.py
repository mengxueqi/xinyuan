from __future__ import annotations

from processors.base import ProcessedDocument


def mark_duplicates(documents: list[ProcessedDocument]) -> list[ProcessedDocument]:
    seen_by_hash: dict[str, str] = {}

    for document in documents:
        if document.content_hash in seen_by_hash:
            document.is_duplicate = True
            document.duplicate_of = seen_by_hash[document.content_hash]
            continue

        seen_by_hash[document.content_hash] = document.url or document.title

    return documents
