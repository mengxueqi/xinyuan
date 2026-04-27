from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
import re

import streamlit as st

from business_db import BusinessDatabase
from tasks.pipeline import (
    run_build_insights_now,
    run_crawl_now,
    run_detect_changes_now,
    run_full_pipeline_now,
    run_process_now,
    run_sync_business_db_now,
)
from utils import format_company_display
from utils import select_focus_events


PROJECT_ROOT = Path(__file__).resolve().parent
BUSINESS_DB_PATH = PROJECT_ROOT / "data" / "business" / "xinyuan.db"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "daily"
FOCUS_EVENT_TYPES = {"product", "financing", "capacity", "ip", "performance"}
FOCUS_EVENT_LIMIT = 20
FOCUS_EVENT_MAX_PER_COMPANY = 6
FOCUS_EVENT_MAX_AGE_DAYS = 60


def get_database() -> BusinessDatabase:
    database = BusinessDatabase(BUSINESS_DB_PATH)
    database.initialize()
    return database


def get_table_counts() -> dict[str, int]:
    database = get_database()
    daily_counts = database.fetch_daily_counts(date.today())
    if not BUSINESS_DB_PATH.exists():
        return {
            "companies": 0,
            "sources": 0,
            "events": 0,
            "change_logs": 0,
            "insight_items": 0,
            "report_runs": 0,
            "task_runs": 0,
            "today_events": 0,
        }

    import sqlite3

    connection = sqlite3.connect(BUSINESS_DB_PATH)
    try:
        cursor = connection.cursor()
        tables = [
            "companies",
            "sources",
            "events",
            "change_logs",
            "insight_items",
            "report_runs",
            "task_runs",
        ]
        counts = {
            table: cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }
    finally:
        connection.close()

    return counts | {"today_events": daily_counts.get("events", 0)}


def get_report_files() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.glob("*.md"), reverse=True)


def parse_report_date(report_name: str) -> date | None:
    try:
        return date.fromisoformat(Path(report_name).stem)
    except ValueError:
        return None


def parse_covered_date(report_content: str) -> date | None:
    match = re.search(r"^- Covered Date:\s*(\d{4}-\d{2}-\d{2})\s*$", report_content, re.MULTILINE)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def parse_report_markdown(report_name: str, report_content: str) -> dict:
    generated_date = parse_report_date(report_name)
    covered_date = parse_covered_date(report_content) or generated_date

    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw_line in report_content.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections[current_section] = []
            continue
        if current_section:
            sections[current_section].append(line)

    overview_lines = sections.get("Overview", [])
    overview = {
        "focus_events": 0,
        "change_logs": 0,
        "insight_items": 0,
    }
    for line in overview_lines:
        if "Focus events:" in line:
            overview["focus_events"] = _extract_trailing_int(line)
        elif "Priority events:" in line:
            overview["focus_events"] = _extract_trailing_int(line)
        elif "Event candidates:" in line:
            overview["focus_events"] = _extract_trailing_int(line)
        elif (
            "Change logs:" in line
            or "Historically new events / page changes:" in line
            or "New events:" in line
        ):
            overview["change_logs"] = _extract_trailing_int(line)
        elif "Insight items:" in line or "Analysis items:" in line or "Change analysis items:" in line:
            overview["insight_items"] = _extract_trailing_int(line)

    return {
        "generated_date": generated_date,
        "covered_date": covered_date,
        "overview": overview,
        "analysis": parse_report_items(sections.get("Analysis", []) or sections.get("Top Insights", [])),
        "change_logs": parse_report_items(sections.get("Change Logs", [])),
        "focus_events": parse_report_items(
            sections.get("Recent Priority Events", [])
            or sections.get("Focus Events", [])
            or sections.get("Event Candidates", [])
        ),
    }


def _extract_trailing_int(line: str) -> int:
    match = re.search(r"(\d+)\s*$", line)
    return int(match.group(1)) if match else 0


def parse_report_items(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    current: dict | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if re.match(r"^\d+\.\s", line) or line.startswith("- "):
            if current:
                items.append(current)
            text = re.sub(r"^\d+\.\s*", "", line)
            text = re.sub(r"^-+\s*", "", text)
            current = {"text": text, "url": None, "score": None, "reason": None, "types": None}
            continue

        if current is None:
            continue

        if line.startswith("- URL:"):
            current["url"] = line.replace("- URL:", "", 1).strip()
        elif line.startswith("- Score:"):
            current["score"] = line.replace("- Score:", "", 1).strip()
        elif line.startswith("- Reason:"):
            current["reason"] = line.replace("- Reason:", "", 1).strip()
        elif line.startswith("- Types:"):
            current["types"] = line.replace("- Types:", "", 1).strip()
        else:
            current["text"] = f"{current['text']} {line}".strip()

    if current:
        items.append(current)
    return items


def render_sidebar() -> None:
    st.sidebar.header("Run Now")
    st.sidebar.caption("Scheduled runs are still handled by `scheduler.py`. Use these buttons for manual runs.")

    if st.sidebar.button("Run Full Pipeline", use_container_width=True):
        with st.spinner("Running full pipeline..."):
            st.session_state["last_log"] = run_full_pipeline_now()

    if st.sidebar.button("Run Crawl", use_container_width=True):
        with st.spinner("Running crawl..."):
            st.session_state["last_log"] = run_crawl_now()

    if st.sidebar.button("Run Process", use_container_width=True):
        with st.spinner("Running processing..."):
            st.session_state["last_log"] = run_process_now()

    if st.sidebar.button("Run Change Detection", use_container_width=True):
        with st.spinner("Running change detection..."):
            st.session_state["last_log"] = run_detect_changes_now()

    if st.sidebar.button("Run Insight Build", use_container_width=True):
        with st.spinner("Building insights..."):
            st.session_state["last_log"] = run_build_insights_now()

    if st.sidebar.button("Sync Business DB", use_container_width=True):
        with st.spinner("Syncing business database..."):
            st.session_state["last_log"] = run_sync_business_db_now()


def render_overview(counts: dict[str, int]) -> None:
    metrics = st.columns(7)
    labels = [
        ("Companies", counts["companies"]),
        ("Sources", counts["sources"]),
        ("Events", counts["events"]),
        ("New Events", counts["change_logs"]),
        ("Analysis", counts["insight_items"]),
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
            if key == "event_types_json" and not value:
                metadata = record.get("metadata_json") or {}
                if isinstance(metadata, dict):
                    value = metadata.get("event_types", [])
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


def render_dataframe_with_links(records: list[dict], keys: list[str]) -> None:
    column_config = None
    if "url" in keys:
        column_config = {
            "url": st.column_config.LinkColumn(
                "url",
                display_text="Open link",
            )
        }

    st.dataframe(
        build_dataframe_rows(records, keys),
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )


def get_change_company_display(record: dict) -> str:
    metadata = record.get("metadata_json") or {}
    return format_company_display(
        record.get("company_name"),
        metadata.get("matched_companies", []) if isinstance(metadata, dict) else [],
    )


def get_change_event_types(record: dict) -> list[str]:
    metadata = record.get("metadata_json") or {}
    event_types = metadata.get("event_types", []) if isinstance(metadata, dict) else []
    return sorted({str(item) for item in event_types if item})


def get_change_published_date(record: dict) -> str:
    metadata = record.get("metadata_json") or {}
    published_at = metadata.get("published_at") if isinstance(metadata, dict) else None
    parsed = parse_iso_date(published_at or record.get("detected_at") or record.get("batch_date"))
    return parsed.isoformat() if parsed else ""


def is_announcement_change(record: dict) -> bool:
    url = str(record.get("url") or "").lower()
    source_name = str(record.get("source_name") or "").lower()
    return (
        "eastmoney.com/notices" in url
        or "/notices/" in url
        or "notice" in source_name
        or "announcement" in source_name
    )


def build_company_distribution(records: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(get_change_company_display(record), []).append(record)

    rows = []
    for company_name, company_records in grouped.items():
        sources = sorted({str(item.get("source_name") or "") for item in company_records if item.get("source_name")})
        rows.append(
            {
                "company_name": company_name,
                "new_events": len(company_records),
                "top_score": max((item.get("importance_score") or 0) for item in company_records),
                "latest_detected": max(str(item.get("detected_at") or item.get("batch_date") or "") for item in company_records),
                "sources": ", ".join(sources[:3]),
            }
        )
    return sorted(rows, key=lambda row: (-row["new_events"], row["company_name"]))


def build_change_clusters(records: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = {}
    for record in records:
        if is_announcement_change(record):
            key = (
                "announcement",
                record.get("company_name") or "",
                record.get("source_name") or "",
                get_change_published_date(record),
            )
        else:
            key = (
                "event",
                record.get("batch_date") or "",
                record.get("company_name") or "",
                record.get("source_name") or "",
                record.get("title") or record.get("summary") or "",
                record.get("url") or "",
            )
        grouped.setdefault(key, []).append(record)

    clusters = []
    for items in grouped.values():
        representative = max(
            items,
            key=lambda item: (
                item.get("importance_score") or 0,
                str(item.get("detected_at") or item.get("batch_date") or ""),
            ),
        )
        company_display = get_change_company_display(representative)
        published_date = get_change_published_date(representative)
        event_types = sorted({event_type for item in items for event_type in get_change_event_types(item)})
        top_score = max((item.get("importance_score") or 0) for item in items)
        is_pack = len(items) > 1 and is_announcement_change(representative)
        title = representative.get("title") or representative.get("summary") or "(untitled event)"
        if is_pack:
            cluster_title = f"{company_display} announcement pack"
            if published_date:
                cluster_title = f"{cluster_title} - {published_date}"
        else:
            cluster_title = title

        clusters.append(
            {
                "cluster_title": cluster_title,
                "company_name": company_display,
                "item_count": len(items),
                "published_date": published_date,
                "event_types": ", ".join(event_types) if event_types else "uncategorized",
                "top_score": top_score,
                "source_name": representative.get("source_name", ""),
                "url": representative.get("url", ""),
                "latest_detected": max(str(item.get("detected_at") or item.get("batch_date") or "") for item in items),
                "summary": (
                    f"Grouped {len(items)} related announcements. Top item: {title}"
                    if is_pack
                    else representative.get("summary", "")
                ),
                "items": sorted(
                    items,
                    key=lambda item: (
                        -(item.get("importance_score") or 0),
                        str(item.get("title") or ""),
                    ),
                ),
            }
        )

    return sorted(
        clusters,
        key=lambda cluster: (
            cluster["latest_detected"],
            cluster["top_score"],
            cluster["item_count"],
        ),
        reverse=True,
    )


def render_company_distribution(records: list[dict]) -> None:
    distribution = build_company_distribution(records)
    if not distribution:
        return

    counter = Counter({row["company_name"]: row["new_events"] for row in distribution})
    top_company, top_count = counter.most_common(1)[0]
    metrics = st.columns(3)
    metrics[0].metric("Raw New Event Rows", len(records))
    metrics[1].metric("Companies", len(distribution))
    metrics[2].metric("Largest Company Share", f"{top_company}: {top_count}")

    st.dataframe(distribution, use_container_width=True, hide_index=True)


def render_clustered_changes(records: list[dict]) -> None:
    clusters = build_change_clusters(records)
    if not clusters:
        st.info("No new events for this filter.")
        return

    st.caption(
        f"Merged {len(records)} raw new-event rows into {len(clusters)} display rows. "
        "Announcement packs group the same company, source, and published date."
    )
    render_dataframe_with_links(
        clusters,
        [
            "cluster_title",
            "company_name",
            "item_count",
            "published_date",
            "event_types",
            "top_score",
            "source_name",
            "summary",
            "url",
        ],
    )

    packed_clusters = [cluster for cluster in clusters if cluster["item_count"] > 1]
    if packed_clusters:
        with st.expander("Announcement Pack Details", expanded=False):
            for cluster in packed_clusters:
                st.markdown(f"**{cluster['cluster_title']}**")
                render_dataframe_with_links(
                    cluster["items"],
                    [
                        "title",
                        "importance_score",
                        "summary",
                        "url",
                    ],
                )


def get_dashboard_filters(database: BusinessDatabase) -> tuple[str, str | None, int]:
    companies = ["All"] + database.list_companies()
    columns = st.columns([1, 1, 1])
    selected_company = columns[0].selectbox("Company", companies, index=0)
    selected_date = columns[1].date_input(
        "Date",
        value=date.today(),
        help="Filter by batch date prefix.",
        key="dashboard_date",
    )
    row_limit = columns[2].slider("Rows", min_value=10, max_value=200, value=50, step=10)
    return selected_company, selected_date.isoformat() if selected_date else None, row_limit


def parse_iso_date(value) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def render_reports_panel() -> None:
    report_files = get_report_files()
    if report_files:
        database = get_database()
        selected_report_name = st.selectbox(
            "Select report",
            options=[report_file.name for report_file in report_files],
            key="report_selector",
        )
        selected_report = REPORTS_DIR / selected_report_name
        report_content = selected_report.read_text(encoding="utf-8")
        report_data = parse_report_markdown(selected_report_name, report_content)
        generated_date = report_data["generated_date"]
        covered_date = report_data["covered_date"]
        overview = report_data["overview"]

        live_counts = (
            database.fetch_daily_counts(covered_date)
            if covered_date
            else {"events": 0, "change_logs": 0, "insight_items": 0}
        )
        live_events = (
            database.fetch_focus_event_candidates(
                covered_date,
                max_age_days=FOCUS_EVENT_MAX_AGE_DAYS,
            )
            if covered_date
            else []
        )
        focus_events = select_focus_events(
            live_events,
            FOCUS_EVENT_TYPES,
            reference_date=covered_date,
            max_items=FOCUS_EVENT_LIMIT,
            max_per_company=FOCUS_EVENT_MAX_PER_COMPANY,
            max_age_days=FOCUS_EVENT_MAX_AGE_DAYS,
        )

        with st.container(border=True):
            st.subheader("Overview")
            if generated_date and covered_date:
                st.caption(
                    f"Generated Date: {generated_date.isoformat()} | Covered Date: {covered_date.isoformat()}"
                )
            overview_cols = st.columns(3)
            overview_cols[0].metric("Focus Events", len(focus_events))
            overview_cols[1].metric(
                "New Events",
                live_counts.get("change_logs", overview.get("change_logs", 0)),
            )
            overview_cols[2].metric("Change Analysis", live_counts.get("insight_items", overview.get("insight_items", 0)))

        with st.container(border=True):
            st.subheader("Focus Events")
            if covered_date:
                st.caption(
                    f"This section is anchored to the covered date ({covered_date.isoformat()}), not the report file name. "
                    "It is selected from the processed event library."
                )
            if focus_events:
                for event in focus_events:
                    company_display = format_company_display(
                        event.get("company_name"),
                        event.get("matched_companies_json", [])
                        or (event.get("metadata_json", {}) or {}).get("matched_companies", []),
                    )
                    title = event.get("title") or "(untitled event)"
                    event_types = event.get("event_types_json") or (event.get("metadata_json", {}) or {}).get("event_types", [])
                    title_line = f"**[{company_display}] {title}**"
                    if event.get("url"):
                        title_line += f" [Open link]({event['url']})"
                    st.markdown(title_line)

                    meta_cols = st.columns(3)
                    meta_cols[0].caption(
                        f"Types: {', '.join(event_types)}" if event_types else "Types: uncategorized"
                    )
                    meta_cols[1].caption(
                        f"Score: {event['importance_score']}"
                        if event.get("importance_score") is not None
                        else "Score: -"
                    )
                    if event.get("published_at"):
                        meta_cols[2].caption(f"Published: {event['published_at']}")
                    elif event.get("detected_at"):
                        meta_cols[2].caption(f"Detected: {str(event['detected_at'])[:10]}")
                    else:
                        meta_cols[2].caption("Published: -")
            else:
                st.write("No focus events were found for this date.")
    else:
        st.info("No reports generated yet.")


def render_event_query_panel(database: BusinessDatabase) -> None:
    st.caption(
        "Search the raw event library directly from `events`, including title and content text. "
        "Multiple keywords use AND logic, and quoted phrases are treated as exact matches."
    )
    controls = st.columns([2, 1, 1])
    keyword = controls[0].text_input(
        "Keywords",
        value=st.session_state.get("event_query_keyword", ""),
        key="event_query_keyword",
        placeholder='e.g. partnership loreal or "pilot plant" enzyme',
    ).strip()
    companies = ["All"] + database.list_companies()
    selected_company = controls[1].selectbox("Company", companies, index=0, key="event_query_company")
    row_limit = controls[2].slider("Rows", min_value=10, max_value=200, value=50, step=10, key="event_query_limit")

    if not keyword:
        st.info("Enter a keyword to search the raw event library.")
        return

    results = database.search_events(keyword, selected_company, row_limit)
    st.caption(f"Matched {len(results)} raw events.")
    display_rows = []
    for row in results:
        display_row = dict(row)
        content_text = str(display_row.get("content_text") or "")
        display_row["content_preview"] = (
            f"{content_text[:280]}..." if len(content_text) > 280 else content_text
        )
        display_rows.append(display_row)
    render_dataframe_with_links(
        display_rows,
        [
            "published_at",
            "batch_date",
            "company_name",
            "source_name",
            "title",
            "content_preview",
            "event_types_json",
            "url",
        ],
    )


def render_dashboard(database: BusinessDatabase) -> None:
    selected_company, date_prefix, row_limit = get_dashboard_filters(database)
    changes = database.fetch_recent_changes(selected_company, date_prefix, row_limit)
    analysis = database.fetch_recent_insights(selected_company, date_prefix, row_limit)

    tabs = st.tabs(["New Events", "Change Analysis"])

    with tabs[0]:
        st.caption(
            "Shows historically new events plus meaningful page or job snapshot changes. "
            "Event changes are compared against the historical event library, not just the previous batch."
        )
        with st.container(border=True):
            st.subheader("Company Distribution")
            render_company_distribution(changes)

        with st.container(border=True):
            st.subheader("Merged New Events")
            render_clustered_changes(changes)

    with tabs[1]:
        st.caption(
            "Scored and summarized intelligence output derived from historically new events and page/job changes."
        )
        render_dataframe_with_links(
            analysis,
            [
                "batch_date",
                "company_name",
                "priority_label",
                "importance_score",
                "summary",
                "reason",
                "url",
            ],
        )

    with st.expander("Advanced Info", expanded=False):
        st.caption("Execution Log")
        st.code(st.session_state.get("last_log", "No manual run yet."), language="text")
        st.caption("Recent Pipeline Status")
        task_runs = database.fetch_recent_task_runs(limit=20)
        if task_runs:
            st.dataframe(
                build_dataframe_rows(
                    task_runs,
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
        else:
            st.info("No task runs recorded yet.")


def main() -> None:
    st.set_page_config(page_title="Xinyuan Monitor", layout="wide")
    st.title("Xinyuan Biomanufacturing Monitor")
    st.caption("Reports first, dashboard second, operational details hidden unless needed.")

    render_sidebar()

    counts = get_table_counts()
    database = get_database()
    render_overview(counts)

    main_tabs = st.tabs(["Report", "Dashboard", "Event Query"])

    with main_tabs[0]:
        render_reports_panel()

    with main_tabs[1]:
        render_dashboard(database)

    with main_tabs[2]:
        render_event_query_panel(database)


if __name__ == "__main__":
    main()
