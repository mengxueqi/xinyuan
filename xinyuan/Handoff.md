# Handoff

This document is for the next maintainer of the project. It summarizes the current architecture, operating model, important implementation choices, and known caveats.

## Project Goal

Monitor a focused set of biomanufacturing companies, capture raw updates from web and capital-market sources, turn them into a historical event library, detect meaningful new events and page changes, score both historically new changes and first-time ingested events, and present the results in a local UI and daily report.

## Current Tracked Companies

- 华恒生物
- 凯赛生物
- 蓝晶微生物
- 川宁生物
- 恩和生物 Bota Bio
- CellX
- 昆山亚香

There is also an `行业通用` bucket in [sources_seed.csv](D:\codex\xinyuan\seeds\sources_seed.csv) for cross-company industry sources such as RSS feeds.

## System Architecture

### 1. Configuration

- [companies_core_seed.csv](D:\codex\xinyuan\seeds\companies_core_seed.csv)
- [sources_seed.csv](D:\codex\xinyuan\seeds\sources_seed.csv)
- [keywords_seed.csv](D:\codex\xinyuan\seeds\keywords_seed.csv)

These are the editable seeds for tracked entities and source behavior.

### 2. Collection

Collectors live in [collectors](D:\codex\xinyuan\collectors).

Key collectors:

- RSS collector
- Generic web/news collector
- Jobs collector
- Eastmoney announcement handling inside the web collector

Important collector behavior:

- News pages attempt to split list pages into article-like items
- Eastmoney announcement pages are handled through a direct API flow
- Placeholder titles such as `读取中,请稍候` are filtered out

### 3. Raw storage

Raw artifacts are written to [data/raw](D:\codex\xinyuan\data\raw) as JSONL.

Main folders:

- `raw_documents`
- `page_snapshots`
- `job_snapshots`
- `crawl_runs`

### 4. Processing

Processing code lives in [processors](D:\codex\xinyuan\processors).

Current processing responsibilities:

- normalization
- de-duplication
- entity/company matching
- event classification
- event candidate filtering

### 5. Change detection

Change detectors live in [detectors](D:\codex\xinyuan\detectors).

This area was materially changed and is important to understand.

#### Current logic

Event changes:

- Current batch events are compared against the **historical event library**
- They are **not** compared only against the previous batch
- They require a valid `published_at`
- They currently use a `60-day` publication window

Page and job changes:

- Still use snapshot comparison logic

This was changed to avoid two recurring problems:

1. Missing a change because an earlier batch failed or was incomplete
2. Treating an old event as new just because it was first captured recently

### 6. Analysis

Insight-building code lives in [insights](D:\codex\xinyuan\insights) and [tasks/build_insights.py](D:\codex\xinyuan\tasks\build_insights.py).

Current role:

- build a processed-event library for all event candidates
- score and summarize change-analysis items for dashboard use
- provide one shared scoring family for both layers

Current semantic contract:

- `summary` = what happened
- `reason` = why it matters
- `score_basis` = why the score landed where it did

`score_basis` is stored in metadata so the main UI stays readable.

### 7. Business database

The SQLite database lives at [data/business/xinyuan.db](D:\codex\xinyuan\data\business\xinyuan.db).

Repository layer:

- [business_db/repository.py](D:\codex\xinyuan\business_db\repository.py)

Main tables:

- `companies`
- `sources`
- `events`
- `change_logs`
- `processed_events`
- `insight_items`
- `alerts`
- `report_runs`
- `task_runs`

Most of the UI reads from this database, not directly from raw JSONL.

### 8. UI

Main UI file:

- [ui_app.py](D:\codex\xinyuan\ui_app.py)

Current top-level sections:

- `Report`
- `Dashboard`
- `Event Query`

Important behaviors:

- `Dashboard` only shows:
  - `New Events`
  - `Change Analysis`
- `Report` only shows:
  - `Focus Events`
- `Report` is anchored by a report file selection, but live focus-event content is pulled from the database for the report's covered date
- `Event Query` searches the raw event library directly
- `Manual Report` has been removed from the UI

## Core Data Semantics

This project has four distinct layers that are easy to confuse.

### `events`

Historical event library.

Meaning:

- "What event-like items has the system captured?"

This is the base event corpus used by `Event Query` and later change detection.

Core event fields:

- `batch_date`
- `company_name`
- `source_name`
- `source_type`
- `url`
- `title`
- `content_text`
- `event_types_json`
- `tech_signals_json`
- `matched_companies_json`
- `matched_focus_keywords_json`
- `is_duplicate`
- `published_at`
- `fetched_at`

### `change_logs`

Current UI wording:

- `New Events`

Underlying meaning:

- historically new events or meaningful page/job changes

Because the UI wording is shorter than the underlying logic, keep this distinction in mind:

- not every row in `change_logs` is literally an event row
- page/job snapshot changes can also live here

### `processed_events`

Processed-event library.

Meaning:

- every event candidate in `events` is summarized, scored, and labeled
- a row can be historically new or not
- this is the source layer for `Focus Events`

Important field meanings:

- `summary`
  - event-level description of what happened
- `reason`
  - why the event is worth attention
- `importance_score`
  - shared numeric score
- `priority_label`
  - `low / medium / high`
- `metadata_json.score_basis`
  - detailed scoring notes

### `insight_items`

Higher-level analysis derived from changes.

Meaning:

- "Why does this change matter?"

This is now a change-analysis table, not the main scored event library.

Important distinction:

- `processed_events` covers all event candidates
- `insight_items` only covers detected changes
- `Report` reads from `processed_events`
- `Dashboard` reads from `change_logs` and `insight_items`

## Focus Events

Focus events are a business view derived from `processed_events`, not from `events` and not from `insight_items`.

Selection is handled in [utils/focus_events.py](D:\codex\xinyuan\utils\focus_events.py).

Current rules:

- only event types in:
  - `product`
  - `financing`
  - `capacity`
  - `ip`
  - `performance`
- maximum `20` rows
- maximum `6` rows per company
- prefer diversity across event types
- enforce recency
- uses the processed-event score plus focus-type weighting

This view is intentionally not the same as `change_logs`.

That distinction matters:

- `Dashboard -> New Events` = change-detection output
- `Dashboard -> Change Analysis` = scored interpretation of those changes
- `Report -> Focus Events` = recent important events selected from `processed_events`

Current practical flow:

1. raw event enters `events`
2. if historically new, it also enters `change_logs`
3. all event candidates are scored into `processed_events`
4. change rows are explained into `insight_items`
5. report focus view is selected from `processed_events`

## Reports

Report generation lives in [tasks/report.py](D:\codex\xinyuan\tasks\report.py).

Current behavior:

- file name uses generated date
- covered data date is written inside the report body
- the report overview contains:
  - Focus events
  - New events
  - Analysis items
- the visible report body currently emphasizes `Focus Events`

Important nuance:

- Report files are static markdown files
- The UI uses the report file as an anchor for `generated_date` and `covered_date`
- Live focus-event content is then queried from the database for the covered date

This was done to avoid stale report-body inconsistencies.

## Scheduling and Pipeline

Scheduler:

- [scheduler.py](D:\codex\xinyuan\scheduler.py)

Pipeline:

- [tasks/pipeline.py](D:\codex\xinyuan\tasks\pipeline.py)

Current schedule:

- `08:30` daily report
- `09:00` scheduled pipeline
- `16:00` scheduled pipeline

Pipeline stages:

1. `crawl_sources`
2. `process_documents`
3. `detect_changes`
4. `build_insights`
5. `sync_business_db`

Recent architecture improvements:

- scheduler triggers a single pipeline run
- stages write into `task_runs`
- logs go to [data/logs](D:\codex\xinyuan\data\logs)

## Listed Company Sources

Current listed-company strategy:

- prefer Eastmoney announcement and finance sources
- Sina sources have been removed from seed config and business sync

Reason:

- Sina pages often exposed placeholder titles and low-value entry pages
- Eastmoney announcement extraction is more reliable for structured notices

If listed-company announcement quality regresses, check:

- [collectors/web_collector.py](D:\codex\xinyuan\collectors\web_collector.py)
- [sources_seed.csv](D:\codex\xinyuan\seeds\sources_seed.csv)
- [utils/focus_events.py](D:\codex\xinyuan\utils\focus_events.py)
- [business_db/repository.py](D:\codex\xinyuan\business_db\repository.py)

## Known Operational Caveats

### 1. New Events count can still feel smaller than raw event volume

This is expected.

Why:

- `events` is the historical event library
- `New Events` is the filtered change layer
- repeated crawls will keep adding or revisiting many `events`, but only some become `New Events`

### 2. Local scripts vs new-machine setup

There are local startup helper scripts in the repo, but they were shaped around the current machine.

For a new machine, prefer:

- `conda env create -f environment.yml`
- `conda activate xinyuan`
- `streamlit run ui_app.py`
- `python scheduler.py`

### 3. Network behavior may differ by execution environment

Some earlier failures with `WinError 10013` were environment-dependent. In restricted execution contexts, network calls may fail even though local UI or local scheduler runs succeed.

If something looks like a collector bug, first check whether it reproduces in the real local environment.

### 4. Reports can be manually regenerated and overwritten

Because report filenames use the generated date, repeated manual tests on the same day can overwrite the same markdown file.

If historical reproducibility becomes important, add a different report naming strategy or archive copies.

### 5. Runtime data can be rebuilt

Most files under [data](D:\codex\xinyuan\data) are runtime artifacts. They should not be treated as source-of-truth configuration.

Configuration truth lives in:

- `companies_core_seed.csv`
- `sources_seed.csv`
- `keywords_seed.csv`
- code under `collectors/`, `processors/`, `detectors/`, `insights/`, `tasks/`

## Typical Maintenance Tasks

### Add a new company

1. Add company row to [companies_core_seed.csv](D:\codex\xinyuan\seeds\companies_core_seed.csv)
2. Add sources to [sources_seed.csv](D:\codex\xinyuan\seeds\sources_seed.csv)
3. Add aliases and keywords to [keywords_seed.csv](D:\codex\xinyuan\seeds\keywords_seed.csv)
4. Sync:

```powershell
conda activate xinyuan
python -c "from tasks.sync_business_db import sync_business_db; print(sync_business_db())"
```

5. Run a pipeline:

```powershell
conda activate xinyuan
python -c "from tasks.pipeline import run_full_pipeline_now; print(run_full_pipeline_now())"
```

### Rebuild changes and analysis after logic changes

If you modify change-detection or insight logic, the safe path is:

1. Clear derived `change_logs` and `insight_items`
2. Rerun:
   - `detect_changes`
   - `build_insights`
   - `sync_business_db`

Be careful not to destroy seed config or raw event history when doing this.

### Validate UI changes

Use the project interpreter, not the system default Python:

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; py_compile.compile('ui_app.py', doraise=True); print('ok')"
```

or, on a new machine:

```powershell
conda activate xinyuan
python -c "import py_compile; py_compile.compile('ui_app.py', doraise=True); print('ok')"
```

## Suggested Next Improvements

If someone continues this project, the most valuable next steps are probably:

1. Make the `New Events` publication window configurable instead of hard-coded
2. Improve report reproducibility and archiving
3. Add stronger source-level parsing for more company news pages
4. Add explicit UI filters for capital-market sources
5. Add better inspection views for raw source failures
6. Consider a more formal schema for historical event identity keys

## Quick Entry Points

If you only have five minutes:

- read [README.md](D:\codex\xinyuan\README.md) for setup
- read [ui_app.py](D:\codex\xinyuan\ui_app.py) for the main product surface
- read [tasks/pipeline.py](D:\codex\xinyuan\tasks\pipeline.py) for orchestration
- read [business_db/repository.py](D:\codex\xinyuan\business_db\repository.py) for data model and queries
- read [collectors/web_collector.py](D:\codex\xinyuan\collectors\web_collector.py) for the most important source logic
- read [detectors/events.py](D:\codex\xinyuan\detectors\events.py) for the change-detection logic
