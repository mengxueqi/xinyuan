from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from insights.base import InsightRecord, ProcessedEventRecord


class LocalInsightStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.processed_events_dir = self.root_dir / "processed_events"
        self.insight_items_dir = self.root_dir / "insight_items"
        self.insight_runs_dir = self.root_dir / "insight_runs"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for directory in (
            self.root_dir,
            self.processed_events_dir,
            self.insight_items_dir,
            self.insight_runs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def write_batch(
        self,
        batch_key: str,
        processed_events: list[ProcessedEventRecord],
        insights: list[InsightRecord],
        run_started_at: datetime,
    ) -> dict[str, int]:
        processed_events_path = self.processed_events_dir / f"{batch_key}.jsonl"
        processed_rows = [{**asdict(item), "batch_key": batch_key} for item in processed_events]
        if processed_rows:
            self._write_jsonl(processed_events_path, processed_rows)
        elif processed_events_path.exists():
            processed_events_path.unlink()

        insight_items_path = self.insight_items_dir / f"{batch_key}.jsonl"
        insight_rows = [{**asdict(insight), "batch_key": batch_key} for insight in insights]
        if insight_rows:
            self._write_jsonl(insight_items_path, insight_rows)
        elif insight_items_path.exists():
            insight_items_path.unlink()

        self._write_jsonl(
            self.insight_runs_dir / f"{batch_key}.jsonl",
            [
                {
                    "batch_key": batch_key,
                    "run_started_at": run_started_at.isoformat(timespec="seconds"),
                    "batch_date": batch_key,
                    "processed_event_count": len(processed_events),
                    "insight_count": len(insights),
                    "high_priority_count": sum(
                        1 for item in processed_events if item.priority_label == "high"
                    ),
                }
            ],
        )
        return {
            "processed_events": len(processed_events),
            "insight_items": len(insights),
        }

    def _write_jsonl(self, file_path: Path, rows: list[dict]) -> None:
        with file_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
