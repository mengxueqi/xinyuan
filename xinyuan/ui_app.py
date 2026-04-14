from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from business_db import BusinessDatabase
from tasks.pipeline import (
    run_build_insights_now,
    run_crawl_now,
    run_daily_report_now,
    run_detect_changes_now,
    run_full_pipeline_now,
    run_process_now,
    run_sync_business_db_now,
)
from utils import format_company_display


PROJECT_ROOT = Path(__file__).resolve().parent
BUSINESS_DB_PATH = PROJECT_ROOT / "data" / "business" / "xinyuan.db"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "daily"


def get_database() -> BusinessDatabase:
    database = BusinessDatabase(BUSINESS_DB_PATH)
    database.initialize()
    return database


def get_table_counts() -> dict[str, int]:
    database = get_database()
    counts = database.fetch_daily_counts(date.today())
    if not BUSINESS_DB_PATH.exists():
        return {
            "companies": 0,
            "sources": 0,
            "events": 0,
            "change_logs": 0,
            "insight_items": 0,
            "report_runs": 0,
            "task_runs": 0,
        }

    import sqlite3

    connection = sqlite3.connect(BUSINESS_DB_PATH)
    try:
        cursor = connection.cursor()
        tables = ["companies", "sources", "events", "change_logs", "insight_items", "report_runs", "task_runs"]
        base_counts = {
            table: cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }
    finally:
        connection.close()
    return base_counts | {"today_events": counts.get("events", 0)}


def get_report_files() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.glob("*.md"), reverse=True)


def render_sidebar() -> None:
    st.sidebar.header("Actions")
    st.sidebar.caption("Scheduled runs are handled by `scheduler.py`. Use the buttons below for immediate manual runs.")

    if st.sidebar.button("Run Full Pipeline Now", use_container_width=True):
        with st.spinner("Running full pipeline..."):
            st.session_state["last_log"] = run_full_pipeline_now()

    if st.sidebar.button("Run Crawl Only", use_container_width=True):
        with st.spinner("Running crawl..."):
            st.session_state["last_log"] = run_crawl_now()

    if st.sidebar.button("Run Process Only", use_container_width=True):
        with st.spinner("Running processing..."):
            st.session_state["last_log"] = run_process_now()

    if st.sidebar.button("Run Change Detection Only", use_container_width=True):
        with st.spinner("Running change detection..."):
            st.session_state["last_log"] = run_detect_changes_now()

    if st.sidebar.button("Run Insight Build Only", use_container_width=True):
        with st.spinner("Building insights..."):
            st.session_state["last_log"] = run_build_insights_now()

    if st.sidebar.button("Sync Business DB Only", use_container_width=True):
        with st.spinner("Syncing business database..."):
            st.session_state["last_log"] = run_sync_business_db_now()


def render_overview(counts: dict[str, int]) -> None:
    metrics = st.columns(7)
    labels = [
        ("Companies", counts["companies"]),
        ("Sources", counts["sources"]),
        ("Events", counts["events"]),
        ("Changes", counts["change_logs"]),
        ("Insights", counts["insight_items"]),
        ("Reports", counts["report_runs"]),
        ("Task Runs", counts["task_runs"]),
    ]
    for column, (label, value) in zip(metrics, labels):
        column.metric(label, value)


def build_dataframe_rows(records: list[dict], keys: list[str]) -> list[dict]:
    rows = []
    for record in records:
        row = {}
        for key in keys:
            value = record.get(key)
            if isinstance(value, list):
                row[key] = ", ".join(str(item) for item in value)
            else:
                row[key] = value
        if "company_name" in row:
            matched_companies = (
                record.get("matched_companies_json")
                or record.get("metadata_json", {}).get("matched_companies", [])
            )
            row["company_name"] = format_company_display(
                row.get("company_name"),
                matched_companies,
            )
        rows.append(row)
    return rows


def render_data_views(database: BusinessDatabase) -> None:
    st.subheader("Dashboard")
    companies = ["All"] + database.list_companies()
    filters = st.columns([1, 1, 1])
    selected_company = filters[0].selectbox("Company", companies, index=0)
    selected_date = filters[1].date_input(
        "Date filter",
        value=date.today(),
        help="Use a date prefix to inspect a specific day of batches.",
    )
    limit = filters[2].slider("Rows", min_value=10, max_value=200, value=50, step=10)

    date_prefix = selected_date.isoformat() if selected_date else None
    events = database.fetch_recent_events(selected_company, date_prefix, limit)
    changes = database.fetch_recent_changes(selected_company, date_prefix, limit)
    insights = database.fetch_recent_insights(selected_company, date_prefix, limit)

    tabs = st.tabs(["Insights", "Changes", "Events"])

    with tabs[0]:
        st.caption("Scored and summarized monitoring output.")
        st.dataframe(
            build_dataframe_rows(
                insights,
                [
                    "batch_date",
                    "company_name",
                    "priority_label",
                    "importance_score",
                    "summary",
                    "reason",
                    "url",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[1]:
        st.caption("Detected changes between batches.")
        st.dataframe(
            build_dataframe_rows(
                changes,
                [
                    "batch_date",
                    "company_name",
                    "change_type",
                    "importance_score",
                    "summary",
                    "changed_ratio",
                    "url",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[2]:
        st.caption("Processed event candidates synced into the business database.")
        st.dataframe(
            build_dataframe_rows(
                events,
                [
                    "batch_date",
                    "company_name",
                    "source_name",
                    "title",
                    "event_types_json",
                    "tech_signals_json",
                    "url",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_reports_panel() -> None:
    st.subheader("Reports")
    report_files = get_report_files()
    if report_files:
        selected_report_name = st.selectbox(
            "Select a report",
            options=[report_file.name for report_file in report_files],
        )
        selected_report = REPORTS_DIR / selected_report_name
        st.markdown(selected_report.read_text(encoding="utf-8"))
    else:
        st.info("No reports generated yet.")


def render_task_runs(database: BusinessDatabase) -> None:
    st.subheader("Recent Pipeline Status")
    records = database.fetch_recent_task_runs(limit=20)
    if not records:
        st.info("No task runs recorded yet.")
        return

    st.dataframe(
        build_dataframe_rows(
            records,
            [
                "batch_key",
                "stage_name",
                "status",
                "started_at",
                "finished_at",
                "message",
                "error_text",
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    st.set_page_config(page_title="Xinyuan Monitor", layout="wide")
    st.title("Xinyuan Biomanufacturing Monitor")
    st.caption(
        "Use scheduled jobs for routine runs, and the buttons below for immediate manual runs."
    )

    render_sidebar()

    counts = get_table_counts()
    database = get_database()
    render_overview(counts)

    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Manual Report")
        selected_date = st.date_input(
            "Generate report for date",
            value=date.today() - timedelta(days=1),
        )
        if st.button("Generate Report For Selected Date", use_container_width=True):
            with st.spinner("Generating report..."):
                st.session_state["last_log"] = run_daily_report_now(selected_date)

        st.subheader("Execution Log")
        st.code(st.session_state.get("last_log", "No manual run yet."), language="text")
        render_task_runs(database)

    with right:
        render_reports_panel()

    st.divider()
    render_data_views(database)


if __name__ == "__main__":
    main()
