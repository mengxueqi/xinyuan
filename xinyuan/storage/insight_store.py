from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from insights.base import InsightRecord


class LocalInsightStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.insight_items_dir = self.root_dir / "insight_items"
        self.insight_runs_dir = self.root_dir / "insight_runs"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for directory in (
            self.root_dir,
            self.insight_items_dir,
            self.insight_runs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def write_batch(
        self,
        batch_key: str,
        insights: list[InsightRecord],
        run_started_at: datetime,
    ) -> dict[str, int]:
        self._write_jsonl(
            self.insight_items_dir / f"{batch_key}.jsonl",
            [{**asdict(insight), "batch_key": batch_key} for insight in insights],
        )
        self._write_jsonl(
            self.insight_runs_dir / f"{batch_key}.jsonl",
            [
                {
                    "batch_key": batch_key,
                    "run_started_at": run_started_at.isoformat(timespec="seconds"),
                    "batch_date": batch_key,
                    "insight_count": len(insights),
                    "high_priority_count": sum(
                        1 for insight in insights if insight.priority_label == "high"
                    ),
                }
            ],
        )
        return {"insight_items": len(insights)}

    def _write_jsonl(self, file_path: Path, rows: list[dict]) -> None:
        with file_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
