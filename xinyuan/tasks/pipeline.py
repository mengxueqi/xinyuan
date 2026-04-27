from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from business_db import BusinessDatabase
from tasks.build_insights import build_insights
from tasks.crawl import crawl_sources
from tasks.detect_changes import detect_changes
from tasks.process import process_documents
from tasks.report import generate_daily_report
from tasks.sync_business_db import sync_business_db
from utils import get_logger, make_batch_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_DB_PATH = PROJECT_ROOT / "data" / "business" / "xinyuan.db"
LOG_DIR = PROJECT_ROOT / "data" / "logs"


def generate_report_stage(batch_keys: list[str] | None = None, logger=None) -> dict[str, Any]:
    output_path = generate_daily_report(logger=logger)
    return {
        "processed_batches": batch_keys or [],
        "output_path": str(output_path),
    }


PIPELINE_STAGES: tuple[tuple[str, Callable[..., dict[str, Any]]], ...] = (
    ("crawl_sources", crawl_sources),
    ("process_documents", process_documents),
    ("detect_changes", detect_changes),
    ("build_insights", build_insights),
    ("sync_business_db", sync_business_db),
    ("generate_daily_report", generate_report_stage),
)


def _build_database() -> BusinessDatabase:
    database = BusinessDatabase(BUSINESS_DB_PATH)
    database.initialize()
    return database


def _determine_stage_status(result: dict[str, Any]) -> str:
    if result.get("skipped"):
        return "skipped"
    if result.get("failure_count", 0) > 0 and result.get("success_count", 0) == 0:
        return "failed"
    if result.get("failure_count", 0) > 0:
        return "completed_with_errors"
    return "completed"


def _summarize_stage_result(stage_name: str, result: dict[str, Any]) -> str:
    if result.get("skipped"):
        return f"{stage_name}: skipped"

    processed_batches = result.get("processed_batches") or result.get("synced_batches") or []
    if stage_name == "crawl_sources":
        return (
            f"{stage_name}: total={result.get('total_sources', 0)}, "
            f"success={result.get('success_count', 0)}, failure={result.get('failure_count', 0)}"
        )
    if stage_name == "generate_daily_report" and result.get("output_path"):
        return f"{stage_name}: output={result['output_path']}"
    if processed_batches:
        return f"{stage_name}: batches={', '.join(processed_batches)}"
    return f"{stage_name}: completed"


def _serialize_stage_result(result: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(result)
    for key, value in list(serialized.items()):
        if isinstance(value, Path):
            serialized[key] = str(value)
    return serialized


def _run_stage(
    database: BusinessDatabase,
    run_logger,
    run_batch_key: str,
    stage_name: str,
    task: Callable[..., dict[str, Any]],
    **kwargs,
) -> dict[str, Any]:
    started_at = datetime.now()
    database.upsert_task_run(
        batch_key=run_batch_key,
        stage_name=stage_name,
        status="running",
        started_at=started_at.isoformat(timespec="seconds"),
        message=f"{stage_name} started",
    )
    run_logger.info("Stage start | batch=%s | stage=%s", run_batch_key, stage_name)

    try:
        result = task(**kwargs)
        status = _determine_stage_status(result)
        message = _summarize_stage_result(stage_name, result)
        finished_at = datetime.now().isoformat(timespec="seconds")
        database.upsert_task_run(
            batch_key=run_batch_key,
            stage_name=stage_name,
            status=status,
            started_at=started_at.isoformat(timespec="seconds"),
            finished_at=finished_at,
            message=message,
            metadata=_serialize_stage_result(result),
        )
        run_logger.info(
            "Stage complete | batch=%s | stage=%s | status=%s | message=%s",
            run_batch_key,
            stage_name,
            status,
            message,
        )
        return {
            "stage_name": stage_name,
            "status": status,
            "message": message,
            "result": result,
        }
    except Exception as exc:
        finished_at = datetime.now().isoformat(timespec="seconds")
        error_text = str(exc)
        database.upsert_task_run(
            batch_key=run_batch_key,
            stage_name=stage_name,
            status="failed",
            started_at=started_at.isoformat(timespec="seconds"),
            finished_at=finished_at,
            message=f"{stage_name}: failed",
            error_text=error_text,
            metadata={"error_type": type(exc).__name__},
        )
        run_logger.exception("Stage failed | batch=%s | stage=%s", run_batch_key, stage_name)
        return {
            "stage_name": stage_name,
            "status": "failed",
            "message": f"{stage_name}: failed ({error_text})",
            "result": {"error": error_text},
        }


def run_pipeline(batch_key: str | None = None, logger=None) -> dict[str, Any]:
    started_at = datetime.now()
    effective_batch_key = batch_key or make_batch_key(started_at)
    logger = logger or get_logger(LOG_DIR, "xinyuan.pipeline")
    database = _build_database()

    logger.info(
        "Pipeline start | batch=%s | started_at=%s",
        effective_batch_key,
        started_at.isoformat(timespec="seconds"),
    )

    stage_results: list[dict[str, Any]] = []

    crawl_stage = _run_stage(
        database,
        logger,
        effective_batch_key,
        "crawl_sources",
        crawl_sources,
        batch_key=effective_batch_key,
        logger=logger,
    )
    stage_results.append(crawl_stage)
    if crawl_stage["status"] == "failed":
        overall_status = "failed"
    else:
        dependent_stages = (
            ("process_documents", process_documents),
            ("detect_changes", detect_changes),
            ("build_insights", build_insights),
            ("sync_business_db", sync_business_db),
            ("generate_daily_report", generate_report_stage),
        )
        overall_status = "completed"
        for stage_name, task in dependent_stages:
            stage_result = _run_stage(
                database,
                logger,
                effective_batch_key,
                stage_name,
                task,
                batch_keys=[effective_batch_key],
                logger=logger,
            )
            stage_results.append(stage_result)
            if stage_result["status"] == "failed":
                overall_status = "failed"
                break
            if stage_result["status"] == "completed_with_errors":
                overall_status = "completed_with_errors"

    if overall_status != "failed" and any(
        stage["status"] == "completed_with_errors" for stage in stage_results
    ):
        overall_status = "completed_with_errors"

    finished_at = datetime.now()
    logger.info(
        "Pipeline complete | batch=%s | status=%s | duration_seconds=%.2f",
        effective_batch_key,
        overall_status,
        (finished_at - started_at).total_seconds(),
    )
    return {
        "batch_key": effective_batch_key,
        "status": overall_status,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "stage_results": stage_results,
    }


def _format_pipeline_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"batch_key: {summary['batch_key']}",
        f"status: {summary['status']}",
        f"started_at: {summary['started_at']}",
        f"finished_at: {summary['finished_at']}",
        "",
        "stages:",
    ]
    for stage in summary.get("stage_results", []):
        lines.append(f"- {stage['stage_name']}: {stage['status']}")
        lines.append(f"  {stage['message']}")
        result = stage.get("result", {})
        if result:
            lines.append(f"  result: {json.dumps(result, ensure_ascii=False, default=str)}")
    return "\n".join(lines)


def _format_stage_only_summary(batch_key: str, stage_result: dict[str, Any]) -> str:
    summary = {
        "batch_key": batch_key,
        "status": stage_result["status"],
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "stage_results": [stage_result],
    }
    return _format_pipeline_summary(summary)


def run_crawl_now() -> str:
    batch_key = make_batch_key(datetime.now())
    logger = get_logger(LOG_DIR, "xinyuan.pipeline")
    stage_result = _run_stage(
        _build_database(),
        logger,
        batch_key,
        "crawl_sources",
        crawl_sources,
        batch_key=batch_key,
        logger=logger,
    )
    return _format_stage_only_summary(batch_key, stage_result)


def run_process_now() -> str:
    batch_key = f"manual-process-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
    logger = get_logger(LOG_DIR, "xinyuan.pipeline")
    stage_result = _run_stage(
        _build_database(),
        logger,
        batch_key,
        "process_documents",
        process_documents,
        logger=logger,
    )
    return _format_stage_only_summary(batch_key, stage_result)


def run_detect_changes_now() -> str:
    batch_key = f"manual-detect-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
    logger = get_logger(LOG_DIR, "xinyuan.pipeline")
    stage_result = _run_stage(
        _build_database(),
        logger,
        batch_key,
        "detect_changes",
        detect_changes,
        logger=logger,
    )
    return _format_stage_only_summary(batch_key, stage_result)


def run_build_insights_now() -> str:
    batch_key = f"manual-insights-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
    logger = get_logger(LOG_DIR, "xinyuan.pipeline")
    stage_result = _run_stage(
        _build_database(),
        logger,
        batch_key,
        "build_insights",
        build_insights,
        logger=logger,
    )
    return _format_stage_only_summary(batch_key, stage_result)


def run_sync_business_db_now() -> str:
    batch_key = f"manual-sync-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
    logger = get_logger(LOG_DIR, "xinyuan.pipeline")
    stage_result = _run_stage(
        _build_database(),
        logger,
        batch_key,
        "sync_business_db",
        sync_business_db,
        logger=logger,
    )
    return _format_stage_only_summary(batch_key, stage_result)


def run_daily_report_now(report_date: date | None = None) -> str:
    logger = get_logger(LOG_DIR, "xinyuan.report")
    output_path = generate_daily_report(report_date, logger=logger)
    return f"daily_report: completed\noutput_path: {output_path}"


def run_full_pipeline_now() -> str:
    return _format_pipeline_summary(run_pipeline())


def run_scheduled_pipeline() -> dict[str, Any]:
    logger = get_logger(LOG_DIR, "xinyuan.pipeline")
    return run_pipeline(logger=logger)
