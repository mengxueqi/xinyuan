from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from detectors.base import ChangeRecord


class LocalChangeStorage:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.change_logs_dir = self.root_dir / "change_logs"
        self.detection_runs_dir = self.root_dir / "detection_runs"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for directory in (
            self.root_dir,
            self.change_logs_dir,
            self.detection_runs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def write_batch(
        self,
        batch_key: str,
        changes: list[ChangeRecord],
        run_started_at: datetime,
    ) -> dict[str, int]:
        self._write_jsonl(
            self.change_logs_dir / f"{batch_key}.jsonl",
            [{**asdict(change), "batch_key": batch_key} for change in changes],
        )
        self._write_jsonl(
            self.detection_runs_dir / f"{batch_key}.jsonl",
            [
                {
                    "batch_key": batch_key,
                    "run_started_at": run_started_at.isoformat(timespec="seconds"),
                    "batch_date": batch_key,
                    "change_count": len(changes),
                    "new_event_count": sum(
                        1 for change in changes if change.change_type == "new_event"
                    ),
                    "page_change_count": sum(
                        1 for change in changes if change.change_type == "page_change"
                    ),
                    "job_change_count": sum(
                        1 for change in changes if change.change_type == "job_change"
                    ),
                }
            ],
        )
        return {"change_logs": len(changes)}

    def _write_jsonl(self, file_path: Path, rows: list[dict]) -> None:
        with file_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
