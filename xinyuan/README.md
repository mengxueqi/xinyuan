# Xinyuan Biomanufacturing Monitor

Local monitoring system for selected biomanufacturing companies. The project collects company and capital-market updates, normalizes raw content, stores a historical event library, detects new events and page changes, analyzes and scores both new changes and first-time ingested events, and exposes a local Streamlit UI.

## What This Project Does

- Tracks a curated set of companies and industry sources
- Collects raw data from web pages, news hubs, RSS feeds, jobs pages, and listed-company announcement sources
- Builds a historical event library in SQLite
- Detects `New Events`
- Builds a processed-event library for all event candidates
- Builds `Change Analysis` items from detected changes
- Generates a daily report
- Provides a local UI for browsing reports, searching events, and reviewing results

Current tracked companies:

- 华恒生物
- 凯赛生物
- 蓝晶微生物
- 川宁生物
- 恩和生物 Bota Bio
- CellX
- 昆山亚香

## Repository Layout

- [ui_app.py](D:\codex\xinyuan\ui_app.py): Streamlit UI
- [scheduler.py](D:\codex\xinyuan\scheduler.py): APScheduler entrypoint
- [tasks](D:\codex\xinyuan\tasks): crawl, process, detect changes, build insights, report, sync
- [collectors](D:\codex\xinyuan\collectors): RSS, web, jobs, and Eastmoney handling
- [processors](D:\codex\xinyuan\processors): normalization, matching, classification, dedupe
- [detectors](D:\codex\xinyuan\detectors): event/page/job change detection
- [insights](D:\codex\xinyuan\insights): scoring, summarization, reasoning
- [business_db](D:\codex\xinyuan\business_db): SQLite repository layer
- [storage](D:\codex\xinyuan\storage): JSONL storage helpers
- [utils](D:\codex\xinyuan\utils): focus-event logic, logging, formatting helpers
- [data](D:\codex\xinyuan\data): runtime artifacts, reports, logs, database
- [seeds](D:\codex\xinyuan\seeds): all seed files
- [seeds\companies_core_seed.csv](D:\codex\xinyuan\seeds\companies_core_seed.csv): company seed config
- [seeds\sources_seed.csv](D:\codex\xinyuan\seeds\sources_seed.csv): source seed config
- [seeds\keywords_seed.csv](D:\codex\xinyuan\seeds\keywords_seed.csv): alias and keyword seed config
- [launchers](D:\codex\xinyuan\launchers): local startup scripts and bootstrap entrypoints

## Recommended Setup

Use [environment.yml](D:\codex\xinyuan\environment.yml) on a new machine.

Why:

- It pins the Python version
- It recreates the environment in one command
- It is safer than copying the local `.venv`
- It avoids machine-specific path assumptions from old startup scripts

[requirements.txt](D:\codex\xinyuan\requirements.txt) is still useful, but it only describes Python packages.

## Prerequisites

Install:

1. Git
2. Miniconda or Anaconda

Recommended:

- Windows 10 or Windows 11
- PowerShell
- Chrome or Edge

## New Machine Setup

### 1. Clone the repository

```powershell
git clone <your-repo-url>
cd xinyuan
```

### 2. Create the environment

```powershell
conda env create -f environment.yml
```

### 3. Activate the environment

```powershell
conda activate xinyuan
```

### 4. Verify the environment

```powershell
python --version
python -c "import streamlit, requests, bs4, feedparser, apscheduler; print('ok')"
```

## Running the Project

### Run the UI

```powershell
conda activate xinyuan
streamlit run ui_app.py
```

Open [http://localhost:8501](http://localhost:8501).

### Run the scheduler

```powershell
conda activate xinyuan
python scheduler.py
```

Current schedule in [scheduler.py](D:\codex\xinyuan\scheduler.py):

- `08:30` generate daily report
- `09:00` run scheduled pipeline
- `16:00` run scheduled pipeline

### Run both

Use two terminals:

Terminal 1:

```powershell
conda activate xinyuan
streamlit run ui_app.py
```

Terminal 2:

```powershell
conda activate xinyuan
python scheduler.py
```

## Manual Operations

Most day-to-day operations can be triggered from the UI sidebar. If you prefer terminal commands:

### Run the full pipeline now

```powershell
conda activate xinyuan
python -c "from tasks.pipeline import run_full_pipeline_now; print(run_full_pipeline_now())"
```

### Sync seed config into the business database

```powershell
conda activate xinyuan
python -c "from tasks.sync_business_db import sync_business_db; print(sync_business_db())"
```

### Generate a report manually from code

```powershell
conda activate xinyuan
python -c "from tasks.pipeline import run_daily_report_now; print(run_daily_report_now())"
```

Note:

- The UI no longer has a dedicated `Manual Report` tab
- Manual report generation still exists at the task level

## Core Data Flow

The scheduled pipeline runs in this order:

1. `crawl_sources`
2. `process_documents`
3. `detect_changes`
4. `build_insights`
5. `sync_business_db`

Current architecture:

- `events` = historical event library
- `change_logs` = new events or meaningful page/job changes
- `processed_events` = analyzed and scored event library, including first-time ingested events
- `insight_items` = change-analysis output built from `change_logs`

In plain language:

- raw event-like items first enter `events`
- historically new changes are written to `change_logs`
- every event candidate is analyzed and scored into `processed_events`
- dashboard-facing change analysis is written to `insight_items`
- report focus events are selected from `processed_events`

## Event Library

The historical event library is stored in the `events` table inside [xinyuan.db](D:\codex\xinyuan\data\business\xinyuan.db).

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

In plain language:

- `events` answers: "What event-like items has the system captured?"
- It is the base library for search and later change detection

## New Events Logic

UI wording:

- `New Events`

Current change-detection logic:

- The current batch is compared against the **historical event library**
- It is **not** only compared against the immediately previous batch
- Event changes require a valid `published_at`
- Event changes currently use a `60-day` publication window
- Page and job snapshot changes still rely on snapshot comparison

This design avoids two common problems:

1. Missing a change because one earlier batch failed or was incomplete
2. Treating a very old event as new just because it was first captured now

## Processed Event Logic

The project now has a distinct processed-event layer between raw event capture and focus extraction.

Meaning:

- every event candidate in `events` is summarized, scored, and labeled
- historically new events are flagged inside this layer
- the same scoring family is reused for change analysis and focus selection

Key fields:

- `summary` = what happened
- `reason` = why the system thinks the event is worth attention
- `importance_score` = numeric score
- `priority_label` = `low / medium / high`
- `metadata.score_basis` = rule-level scoring basis

This layer is stored in:

- `data/insights/processed_events`
- `processed_events` table in [xinyuan.db](D:\codex\xinyuan\data\business\xinyuan.db)

## Focus Events Logic

`Focus Events` are selected from the processed-event library, not directly from raw events and not from change analysis.

Current rules:

- Allowed priority event types:
  - `product`
  - `financing`
  - `capacity`
  - `ip`
  - `performance`
- 60-day publication window
- Maximum `20` rows
- Maximum `6` rows per company
- Prefer diversity across companies and event types
- Ranking uses processed-event score plus focus-type weighting

Practical distinction:

- `New Events` = historically new changes
- `Change Analysis` = scored interpretation of those changes
- `Focus Events` = recent priority events selected from the processed-event library

## UI Responsibilities

Current UI responsibilities are intentionally split:

- `Dashboard`
  - `New Events`
  - `Change Analysis`
- `Report`
  - `Focus Events`
- `Event Query`
  - raw event-library search

This keeps the dashboard focused on change monitoring while the report focuses on the priority-event view.

## Change Analysis Semantics

`Change Analysis` is intentionally narrower than the processed-event library.

It only explains rows that came from `change_logs`.

Current semantics:

- `summary`
  - describes what changed
- `reason`
  - explains why that change is worth attention
- `score_basis`
  - stored in metadata, not shown by default in the main UI
  - explains how the score was computed

This avoids mixing business judgment with raw scoring notes in the main display.

## Event Query

The `Event Query` page searches the raw event library directly from the `events` table.

Current behavior:

- Searches `title` and `content_text`
- Supports multiple keywords with `AND` logic
- Supports quoted phrases
- Does not depend on `change_logs`

This is useful when you want to inspect the event corpus rather than only current changes.

## Listed Company Sources

For listed companies, the project now prefers Eastmoney-based sources.

Current status:

- Eastmoney announcement and finance sources are the primary listed-company sources
- Sina sources have been removed from seed config and business sync
- Invalid placeholder titles such as `读取中,请稍候` should no longer enter the event pipeline

## Runtime Data

Runtime output lives under [data](D:\codex\xinyuan\data):

- [data/raw](D:\codex\xinyuan\data\raw): raw collected documents and snapshots
- [data/processed](D:\codex\xinyuan\data\processed): normalized documents and event candidates
- [data/changes](D:\codex\xinyuan\data\changes): detected changes
- [data/insights](D:\codex\xinyuan\data\insights): processed-event and change-analysis output
- [data/business/xinyuan.db](D:\codex\xinyuan\data\business\xinyuan.db): SQLite business database
- [data/reports/daily](D:\codex\xinyuan\data\reports\daily): generated reports
- [data/logs](D:\codex\xinyuan\data\logs): runtime logs

Generated runtime files are ignored by Git and can be recreated by rerunning the pipeline.

## Configuration Files

### Companies

Edit [companies_core_seed.csv](D:\codex\xinyuan\seeds\companies_core_seed.csv) to add or update tracked companies.

### Sources

Edit [sources_seed.csv](D:\codex\xinyuan\seeds\sources_seed.csv) to add or update:

- official websites
- news pages
- jobs pages
- Eastmoney announcement pages
- Eastmoney finance pages
- RSS sources

### Keywords

Edit [keywords_seed.csv](D:\codex\xinyuan\seeds\keywords_seed.csv) to update:

- company aliases
- event keywords
- technical keywords
- focus keywords

After changing seed files, resync:

```powershell
conda activate xinyuan
python -c "from tasks.sync_business_db import sync_business_db; print(sync_business_db())"
```

## Troubleshooting

### `conda: command not found`

Install Miniconda or Anaconda first, then reopen the terminal.

### UI opens but the page is unavailable

Make sure the environment is activated and run:

```powershell
streamlit run ui_app.py
```

Then open [http://localhost:8501](http://localhost:8501).

### Scheduler does not run when the machine is off

This is expected. The scheduler only runs while the machine is on and the process is alive.

### Source connectivity is inconsistent

If a crawl works in the local UI but fails in a restricted environment, the problem may be environment-level network restrictions rather than the collector logic.

### Old startup scripts

Files such as:

- [start_ui.ps1](D:\codex\xinyuan\launchers\start_ui.ps1)
- [start_ui.cmd](D:\codex\xinyuan\launchers\start_ui.cmd)
- [start_scheduler.ps1](D:\codex\xinyuan\launchers\start_scheduler.ps1)
- [start_scheduler.cmd](D:\codex\xinyuan\launchers\start_scheduler.cmd)

were originally built around the local `.venv` setup on this machine.

On a new machine, the safest path is:

- recreate the environment from [environment.yml](D:\codex\xinyuan\environment.yml)
- start with `streamlit run ui_app.py`
- start with `python scheduler.py`

## Where To Look Next

If you are using the project:

- Start with this README
- Then open the UI

If you are maintaining the project:

- Read [Handoff.md](D:\codex\xinyuan\Handoff.md)
