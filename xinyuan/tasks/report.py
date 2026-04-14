from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from business_db import BusinessDatabase
from utils import get_logger
from utils import format_company_display


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_DB_PATH = PROJECT_ROOT / "data" / "business" / "xinyuan.db"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "daily"
LOG_DIR = PROJECT_ROOT / "data" / "logs"


def render_markdown_report(
    report_date: date,
    counts: dict[str, int],
    insights: list[dict],
    changes: list[dict],
    events: list[dict],
) -> str:
    lines = [
        f"# Biomanufacturing Daily Report - {report_date.isoformat()}",
        "",
        "## Overview",
        f"- Event candidates: {counts.get('events', 0)}",
        f"- Change logs: {counts.get('change_logs', 0)}",
        f"- Insight items: {counts.get('insight_items', 0)}",
        "",
        "## Top Insights",
        "",
    ]

    if insights:
        for index, insight in enumerate(insights[:10], start=1):
            company_display = format_company_display(
                insight.get("company_name"),
                insight.get("metadata_json", {}).get("matched_companies", []),
            )
            lines.append(
                f"{index}. [{company_display}] "
                f"{insight.get('summary', '')}"
            )
            lines.append(f"   - Score: {insight.get('importance_score', 0)}")
            lines.append(f"   - Reason: {insight.get('reason', '')}")
            if insight.get("url"):
                lines.append(f"   - URL: {insight['url']}")
    else:
        lines.append("- No insight items were generated for this date.")

    lines.extend(["", "## Change Logs", ""])
    if changes:
        for index, change in enumerate(changes[:10], start=1):
            company_display = format_company_display(
                change.get("company_name"),
                change.get("metadata_json", {}).get("matched_companies", []),
            )
            lines.append(
                f"{index}. [{company_display}] "
                f"{change.get('summary', '')}"
            )
            if change.get("url"):
                lines.append(f"   - URL: {change['url']}")
    else:
        lines.append("- No change logs were detected for this date.")

    lines.extend(["", "## Event Candidates", ""])
    if events:
        for index, event in enumerate(events[:10], start=1):
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
        lines.append("- No event candidates were found for this date.")

    lines.append("")
    return "\n".join(lines)


def generate_daily_report(report_date: date | None = None, logger=None) -> Path:
    now = datetime.now()
    effective_report_date = report_date or (now - timedelta(days=1)).date()
    logger = logger or get_logger(LOG_DIR, "xinyuan.report")
    logger.info(
        "generate_daily_report start | report_date=%s",
        effective_report_date.isoformat(),
    )

    database = BusinessDatabase(BUSINESS_DB_PATH)
    database.initialize()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    counts = database.fetch_daily_counts(effective_report_date)
    insights = database.fetch_daily_insights(effective_report_date, limit=20)
    changes = database.fetch_daily_changes(effective_report_date, limit=20)
    events = database.fetch_daily_events(effective_report_date, limit=20)

    report_markdown = render_markdown_report(
        effective_report_date, counts, insights, changes, events
    )
    output_path = REPORTS_DIR / f"{effective_report_date.isoformat()}.md"
    output_path.write_text(report_markdown, encoding="utf-8")

    status = "completed" if any(counts.values()) else "no_data"
    database.upsert_report_run(
        report_date=effective_report_date,
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
