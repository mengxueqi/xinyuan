from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from collectors.base import CollectedItem, SourceConfig
from utils import make_batch_key


class LocalRawStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.raw_documents_dir = self.root_dir / "raw_documents"
        self.page_snapshots_dir = self.root_dir / "page_snapshots"
        self.job_snapshots_dir = self.root_dir / "job_snapshots"
        self.crawl_runs_dir = self.root_dir / "crawl_runs"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for directory in (
            self.root_dir,
            self.raw_documents_dir,
            self.page_snapshots_dir,
            self.job_snapshots_dir,
            self.crawl_runs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def persist_items(
        self,
        source: SourceConfig,
        items: list[CollectedItem],
        run_started_at: datetime,
        batch_key: str | None = None,
    ) -> dict[str, int]:
        effective_batch_key = batch_key or make_batch_key(run_started_at)
        raw_count = 0
        page_snapshot_count = 0
        job_snapshot_count = 0

        for item in items:
            payload = self._build_raw_document_payload(source, item, run_started_at)
            payload["batch_key"] = effective_batch_key
            self._append_jsonl(self.raw_documents_dir / f"{effective_batch_key}.jsonl", payload)
            raw_count += 1

            if source.source_type == "web" and item.metadata.get("item_kind") == "page_snapshot":
                snapshot_payload = self._build_page_snapshot_payload(
                    source, item, run_started_at
                )
                snapshot_payload["batch_key"] = effective_batch_key
                self._append_jsonl(
                    self.page_snapshots_dir / f"{effective_batch_key}.jsonl", snapshot_payload
                )
                page_snapshot_count += 1

            if source.source_type == "jobs":
                snapshot_payload = self._build_job_snapshot_payload(
                    source, item, run_started_at
                )
                snapshot_payload["batch_key"] = effective_batch_key
                self._append_jsonl(
                    self.job_snapshots_dir / f"{effective_batch_key}.jsonl", snapshot_payload
                )
                job_snapshot_count += 1

        self._append_jsonl(
            self.crawl_runs_dir / f"{effective_batch_key}.jsonl",
            {
                "batch_key": effective_batch_key,
                "run_started_at": run_started_at.isoformat(timespec="seconds"),
                "company_name": source.company_name,
                "source_name": source.source_name,
                "source_type": source.source_type,
                "url": source.url,
                "item_count": len(items),
                "raw_document_count": raw_count,
                "page_snapshot_count": page_snapshot_count,
                "job_snapshot_count": job_snapshot_count,
            },
        )

        return {
            "raw_documents": raw_count,
            "page_snapshots": page_snapshot_count,
            "job_snapshots": job_snapshot_count,
        }

    def _build_raw_document_payload(
        self,
        source: SourceConfig,
        item: CollectedItem,
        run_started_at: datetime,
    ) -> dict[str, Any]:
        item_dict = asdict(item)
        item_dict["content_hash"] = self._hash_text(item.content_text)
        item_dict["source"] = asdict(source)
        item_dict["run_started_at"] = run_started_at.isoformat(timespec="seconds")
        item_dict["stored_at"] = datetime.now().isoformat(timespec="seconds")
        return item_dict

    def _build_page_snapshot_payload(
        self,
        source: SourceConfig,
        item: CollectedItem,
        run_started_at: datetime,
    ) -> dict[str, Any]:
        return {
            "company_name": source.company_name,
            "source_name": source.source_name,
            "page_url": item.url,
            "title": item.title,
            "snapshot_text": item.content_text,
            "snapshot_hash": self._hash_text(item.content_text),
            "run_started_at": run_started_at.isoformat(timespec="seconds"),
            "captured_at": item.fetched_at,
            "metadata": item.metadata,
        }

    def _build_job_snapshot_payload(
        self,
        source: SourceConfig,
        item: CollectedItem,
        run_started_at: datetime,
    ) -> dict[str, Any]:
        return {
            "company_name": source.company_name,
            "source_name": source.source_name,
            "page_url": item.url,
            "title": item.title,
            "snapshot_text": item.content_text,
            "snapshot_hash": self._hash_text(item.content_text),
            "run_started_at": run_started_at.isoformat(timespec="seconds"),
            "captured_at": item.fetched_at,
            "metadata": item.metadata,
        }

    def _append_jsonl(self, file_path: Path, payload: dict[str, Any]) -> None:
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    @staticmethod
    def _hash_text(text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()
