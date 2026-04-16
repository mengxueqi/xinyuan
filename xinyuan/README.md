# Xinyuan Biomanufacturing Monitor

Local monitoring system for biomanufacturing companies. The project collects company and industry updates, processes raw content, detects changes, builds higher-level analysis, stores business records in SQLite, and exposes a local Streamlit UI.

## What This Repo Contains

- `ui_app.py`: local Streamlit dashboard
- `scheduler.py`: APScheduler entrypoint for timed runs
- `tasks/`: crawl, process, change detection, analysis, report, sync pipeline
- `business_db/`: SQLite business database access
- `collectors/`: RSS / web / jobs collectors
- `data/`: runtime output such as raw documents, processed artifacts, reports, logs, and SQLite database
- `companies_core_seed.csv`, `sources_seed.csv`, `keywords_seed.csv`: seed configuration

## Recommended Setup

Use `environment.yml` on a new machine.

Why:

- it pins the Python version
- it recreates the project environment in one command
- it is more portable than copying the current `.venv`

`requirements.txt` is still useful, but it only covers Python packages. It does not define the Python version or the environment name.

## Prerequisites

Install one of the following first:

1. Miniconda or Anaconda
2. Git

Recommended:

- Windows 10/11
- PowerShell
- A browser such as Chrome or Edge

## New Machine Deployment

### 1. Clone the repository

```powershell
git clone <your-repo-url>
cd xinyuan
```

### 2. Create the conda environment

```powershell
conda env create -f environment.yml
```

### 3. Activate the environment

```powershell
conda activate xinyuan
```

### 4. Verify Python and key packages

```powershell
python --version
python -c "import streamlit, requests, bs4, feedparser, apscheduler; print('ok')"
```

## Running the Project

### Option A: Run the UI directly

```powershell
streamlit run ui_app.py
```

Then open:

- [http://localhost:8501](http://localhost:8501)

### Option B: Run the scheduler directly

```powershell
python scheduler.py
```

Current default schedule:

- `08:30` generate daily report
- `09:00` run scheduled pipeline
- `16:00` run scheduled pipeline

### Option C: Run both

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

## Important Note About Existing Windows Startup Scripts

This repository includes local helper scripts such as:

- `start_ui.ps1`
- `start_ui.cmd`
- `start_scheduler.ps1`
- `start_scheduler.cmd`

These scripts were built around the current machine's `.venv` layout. On a new machine, the safest path is:

- do **not** rely on the old `.venv`
- recreate the environment from `environment.yml`
- start the project with `streamlit run ui_app.py` and `python scheduler.py`

If you want, you can later adapt the startup scripts on the new machine after the conda environment is confirmed working.

## Data and Runtime Files

Runtime outputs are stored under `data/`:

- `data/raw/`: raw collected documents and snapshots
- `data/processed/`: normalized documents and event candidates
- `data/changes/`: detected changes
- `data/insights/`: higher-level analysis output
- `data/business/xinyuan.db`: SQLite business database
- `data/reports/daily/`: generated reports
- `data/logs/`: runtime logs

The database and generated runtime files are not required for first-time setup. They will be created as the pipeline runs.

## First-Time Sanity Check

After activation, you can run a basic smoke test:

```powershell
python -c "from business_db import BusinessDatabase; from pathlib import Path; db = BusinessDatabase(Path('data/business/xinyuan.db')); db.initialize(); print('db ok')"
python -c "import ui_app; print('ui ok')"
python -c "import scheduler; print('scheduler ok')"
```

## Updating Dependencies

If you later update packages in `requirements.txt`, also update `environment.yml` so new machines stay reproducible.

## Troubleshooting

### `conda: command not found`

Install Miniconda or Anaconda first, then reopen the terminal.

### `EnvironmentNameNotFound: xinyuan`

Run:

```powershell
conda env create -f environment.yml
```

### UI opens but page is blank or unavailable

Make sure the environment is activated and run:

```powershell
streamlit run ui_app.py
```

Then open:

- [http://localhost:8501](http://localhost:8501)

### Scheduler does not run when the machine is off

This is expected. `scheduler.py` only runs while the machine is on and the process is alive.

## Minimal Daily Commands

Activate and run UI:

```powershell
conda activate xinyuan
streamlit run ui_app.py
```

Activate and run scheduler:

```powershell
conda activate xinyuan
python scheduler.py
```
