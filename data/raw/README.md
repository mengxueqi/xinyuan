# Raw Storage

This directory stores local raw ingestion outputs before any downstream parsing,
classification, or change-detection logic runs.

Subdirectories:

- `raw_documents/`: normalized collected items as JSONL
- `page_snapshots/`: web page snapshots used for future diffing
- `job_snapshots/`: jobs-page snapshots used for future job-change detection
- `crawl_runs/`: per-source crawl execution summaries

Each file is grouped by date, for example `2026-04-13.jsonl`.
