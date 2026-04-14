from __future__ import annotations

from pathlib import Path


def list_batch_keys(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(file_path.stem for file_path in directory.glob("*.jsonl"))


def pending_batch_keys(source_dir: Path, marker_dir: Path) -> list[str]:
    source_keys = set(list_batch_keys(source_dir))
    marker_keys = set(list_batch_keys(marker_dir))
    return sorted(source_keys - marker_keys)
