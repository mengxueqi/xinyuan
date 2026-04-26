# Insight Storage

This directory stores the analysis layer built after change detection.

Subdirectories:

- `processed_events/`: the processed-event library. Every event candidate is summarized, scored, and labeled here, including first-time ingested events that are not historically new changes.
- `insight_items/`: change-analysis records used by the Dashboard. These are the scored summaries of `change_logs`.
- `insight_runs/`: batch-level summaries of the analysis build stage.

Each file is grouped by batch key, for example `2026-04-21T10-05-00.jsonl`.
