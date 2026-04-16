from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from processors.base import ProcessedDocument


class LocalProcessedStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.clean_documents_dir = self.root_dir / "clean_documents"
        self.event_candidates_dir = self.root_dir / "event_candidates"
        self.processing_runs_dir = self.root_dir / "processing_runs"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for directory in (
            self.root_dir,
            self.clean_documents_dir,
            self.event_candidates_dir,
            self.processing_runs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def write_batch(
        self,
        batch_key: str,
        documents: list[ProcessedDocument],
        run_started_at: datetime,
    ) -> dict[str, int]:
        clean_rows = [asdict(document) for document in documents]
        for row in clean_rows:
            row["batch_key"] = batch_key

        event_rows = [
            {
                "batch_key": batch_key,
                "company_name": self._resolve_company_name(document),
                "source_name": document.source_name,
                "source_type": document.source_type,
                "url": document.url,
                "title": document.title,
                "content_text": document.normalized_text[:4000],
                "event_types": document.event_types,
                "tech_signals": document.tech_signals,
                "matched_companies": document.matched_companies,
                "matched_focus_keywords": document.matched_focus_keywords,
                "is_duplicate": document.is_duplicate,
                "published_at": document.published_at,
                "fetched_at": document.fetched_at,
            }
            for document in documents
            if (
                document.event_types
                and not document.is_duplicate
                and document.matched_companies
                and self._is_message_like_event(document)
            )
        ]

        self._write_jsonl(self.clean_documents_dir / f"{batch_key}.jsonl", clean_rows)
        self._write_jsonl(self.event_candidates_dir / f"{batch_key}.jsonl", event_rows)
        self._write_jsonl(
            self.processing_runs_dir / f"{batch_key}.jsonl",
            [
                {
                    "batch_key": batch_key,
                    "run_started_at": run_started_at.isoformat(timespec="seconds"),
                    "batch_date": batch_key,
                    "document_count": len(documents),
                    "event_candidate_count": len(event_rows),
                    "duplicate_count": sum(1 for doc in documents if doc.is_duplicate),
                }
            ],
        )

        return {
            "clean_documents": len(clean_rows),
            "event_candidates": len(event_rows),
        }

    def _write_jsonl(self, file_path: Path, rows: list[dict]) -> None:
        with file_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")

    @staticmethod
    def _resolve_company_name(document: ProcessedDocument) -> str:
        if document.matched_companies:
            return ", ".join(document.matched_companies)
        return document.company_name

    @staticmethod
    def _is_message_like_event(document: ProcessedDocument) -> bool:
        if document.source_type == "rss":
            return True
        if document.source_type != "web":
            return False

        item_kind = str(document.metadata.get("item_kind", "")).lower()
        if item_kind != "article_link":
            return False

        source_page_url = str(document.metadata.get("source_page_url", ""))
        if source_page_url and document.url:
            source_parts = urlparse(source_page_url)
            target_parts = urlparse(document.url)
            if source_parts.netloc and target_parts.netloc:
                if source_parts.netloc != target_parts.netloc:
                    return False
                if target_parts.fragment and target_parts.path == source_parts.path:
                    return False

            if not document.published_at:
                path_blob = " ".join(
                    part.lower()
                    for part in (target_parts.path, target_parts.query)
                    if part
                )
                message_path_hints = (
                    "news",
                    "notice",
                    "announcement",
                    "press",
                    "blog",
                    "article",
                    "show",
                    "env_news",
                    "newsxq",
                    "investor",
                )
                if not any(hint in path_blob for hint in message_path_hints):
                    return False

        return True
