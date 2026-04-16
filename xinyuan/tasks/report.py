from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from business_db import BusinessDatabase
from utils import get_logger
from utils import format_company_display
from utils import select_focus_events


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_DB_PATH = PROJECT_ROOT / "data" / "business" / "xinyuan.db"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "daily"
LOG_DIR = PROJECT_ROOT / "data" / "logs"
FOCUS_EVENT_TYPES = {"product", "financing", "capacity", "ip"}
FOCUS_EVENT_LIMIT = 20
FOCUS_EVENT_MAX_PER_COMPANY = 6
FOCUS_EVENT_MAX_AGE_DAYS = 7


def render_markdown_report(
    generated_date: date,
    covered_date: date,
    counts: dict[str, int],
    focus_events: list[dict],
) -> str:
    lines = [
        f"# Biomanufacturing Daily Report - {generated_date.isoformat()}",
        "",
        f"- Generated Date: {generated_date.isoformat()}",
        f"- Covered Date: {covered_date.isoformat()}",
        "",
        "## Overview",
        f"- Focus events: {len(focus_events)}",
        f"- Change logs: {counts.get('change_logs', 0)}",
        f"- Analysis items: {counts.get('insight_items', 0)}",
        "",
        "## Focus Events",
        "",
    ]

    if focus_events:
        for index, event in enumerate(focus_events[:FOCUS_EVENT_LIMIT], start=1):
            event_types = event.get("event_types_json", [])
            event_text = ", ".join(event_types) if event_types else "uncategorized"
            company_display = format_company_display(
                event.get("company_name"),
                event.get("matched_companies_json", []),
            )
            lines.append(
                f"{index}. [{company_display}] "
                f"{event.get('title', '')}"
            )
            lines.append(f"   - Types: {event_text}")
            if event.get("url"):
                lines.append(f"   - URL: {event['url']}")
    else:
        lines.append("- No focus events were found for this date.")

    lines.append("")
    return "\n".join(lines)


def generate_daily_report(report_date: date | None = None, logger=None) -> Path:
    now = datetime.now()
    generated_date = now.date()
    covered_date = report_date or (generated_date - timedelta(days=1))
    logger = logger or get_logger(LOG_DIR, "xinyuan.report")
    logger.info(
        "generate_daily_report start | generated_date=%s | covered_date=%s",
        generated_date.isoformat(),
        covered_date.isoformat(),
    )

    database = BusinessDatabase(BUSINESS_DB_PATH)
    database.initialize()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    counts = database.fetch_daily_counts(covered_date)
    events = database.fetch_daily_events(covered_date, limit=200)
    focus_events = select_focus_events(
        events,
        FOCUS_EVENT_TYPES,
        reference_date=covered_date,
        max_items=FOCUS_EVENT_LIMIT,
        max_per_company=FOCUS_EVENT_MAX_PER_COMPANY,
        max_age_days=FOCUS_EVENT_MAX_AGE_DAYS,
    )

    report_markdown = render_markdown_report(
        generated_date, covered_date, counts, focus_events
    )
    output_path = REPORTS_DIR / f"{generated_date.isoformat()}.md"
    output_path.write_text(report_markdown, encoding="utf-8")

    status = "completed" if any(counts.values()) else "no_data"
    database.upsert_report_run(
        report_date=generated_date,
        report_type="daily",
        status=status,
        output_path=str(output_path),
    )

    logger.info(
        "Daily report generated | output=%s | status=%s | events=%s | changes=%s | insights=%s",
        output_path,
        status,
        counts.get("events", 0),
        counts.get("change_logs", 0),
        counts.get("insight_items", 0),
    )
    return output_path
