from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable


class BusinessDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL UNIQUE,
                    english_name TEXT,
                    aliases TEXT,
                    country TEXT,
                    region TEXT,
                    category TEXT,
                    sub_sector TEXT,
                    website TEXT,
                    priority TEXT,
                    keywords TEXT,
                    change_signals TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    url TEXT NOT NULL,
                    parser_type TEXT,
                    crawl_frequency TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    priority TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_name, source_name, url)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_date TEXT NOT NULL,
                    company_name TEXT,
                    source_name TEXT,
                    source_type TEXT,
                    url TEXT,
                    title TEXT,
                    event_types_json TEXT,
                    tech_signals_json TEXT,
                    matched_companies_json TEXT,
                    matched_focus_keywords_json TEXT,
                    is_duplicate INTEGER NOT NULL DEFAULT 0,
                    published_at TEXT,
                    fetched_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(batch_date, source_name, title, url)
                );

                CREATE TABLE IF NOT EXISTS change_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_date TEXT NOT NULL,
                    company_name TEXT,
                    source_name TEXT,
                    change_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    title TEXT,
                    summary TEXT,
                    detected_at TEXT,
                    importance_score INTEGER,
                    url TEXT,
                    before_value TEXT,
                    after_value TEXT,
                    changed_ratio REAL,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(batch_date, change_type, source_name, title, url)
                );

                CREATE TABLE IF NOT EXISTS insight_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_date TEXT NOT NULL,
                    company_name TEXT,
                    source_name TEXT,
                    change_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    title TEXT,
                    summary TEXT,
                    importance_score INTEGER,
                    reason TEXT,
                    detected_at TEXT,
                    priority_label TEXT,
                    url TEXT,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(batch_date, change_type, source_name, title, url)
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_date TEXT NOT NULL,
                    company_name TEXT,
                    title TEXT,
                    channel TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS report_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT NOT NULL UNIQUE,
                    report_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    output_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS task_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_key TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    message TEXT,
                    error_text TEXT,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(batch_key, stage_name)
                );

                CREATE INDEX IF NOT EXISTS idx_sources_company_name
                ON sources(company_name);

                CREATE INDEX IF NOT EXISTS idx_events_batch_date
                ON events(batch_date);

                CREATE INDEX IF NOT EXISTS idx_change_logs_batch_date
                ON change_logs(batch_date);

                CREATE INDEX IF NOT EXISTS idx_change_logs_company_name
                ON change_logs(company_name);

                CREATE INDEX IF NOT EXISTS idx_insight_items_batch_date
                ON insight_items(batch_date);

                CREATE INDEX IF NOT EXISTS idx_insight_items_priority_label
                ON insight_items(priority_label);

                CREATE INDEX IF NOT EXISTS idx_task_runs_batch_key
                ON task_runs(batch_key);

                CREATE INDEX IF NOT EXISTS idx_task_runs_stage_name
                ON task_runs(stage_name);
                """
            )

    def seed_companies(self, csv_path: Path) -> int:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO companies (
                    company_name, english_name, aliases, country, region,
                    category, sub_sector, website, priority, keywords,
                    change_signals, notes, updated_at
                ) VALUES (
                    :company_name, :english_name, :aliases, :country, :region,
                    :category, :sub_sector, :website, :priority, :keywords,
                    :change_signals, :notes, CURRENT_TIMESTAMP
                )
                ON CONFLICT(company_name) DO UPDATE SET
                    english_name=excluded.english_name,
                    aliases=excluded.aliases,
                    country=excluded.country,
                    region=excluded.region,
                    category=excluded.category,
                    sub_sector=excluded.sub_sector,
                    website=excluded.website,
                    priority=excluded.priority,
                    keywords=excluded.keywords,
                    change_signals=excluded.change_signals,
                    notes=excluded.notes,
                    updated_at=CURRENT_TIMESTAMP;
                """,
                rows,
            )
        return len(rows)

    def seed_sources(self, csv_path: Path) -> int:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [
                {
                    **row,
                    "is_active": 1 if row.get("is_active", "true").lower() == "true" else 0,
                }
                for row in reader
            ]

        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO sources (
                    company_name, source_name, source_type, url,
                    parser_type, crawl_frequency, is_active, priority,
                    notes, updated_at
                ) VALUES (
                    :company_name, :source_name, :source_type, :url,
                    :parser_type, :crawl_frequency, :is_active, :priority,
                    :notes, CURRENT_TIMESTAMP
                )
                ON CONFLICT(company_name, source_name, url) DO UPDATE SET
                    source_type=excluded.source_type,
                    parser_type=excluded.parser_type,
                    crawl_frequency=excluded.crawl_frequency,
                    is_active=excluded.is_active,
                    priority=excluded.priority,
                    notes=excluded.notes,
                    updated_at=CURRENT_TIMESTAMP;
                """,
                rows,
            )
        return len(rows)

    def sync_events(self, directory: Path) -> int:
        return self._sync_jsonl_directory(
            directory=directory,
            table_name="events",
            columns=(
                "batch_date",
                "company_name",
                "source_name",
                "source_type",
                "url",
                "title",
                "event_types_json",
                "tech_signals_json",
                "matched_companies_json",
                "matched_focus_keywords_json",
                "is_duplicate",
                "published_at",
                "fetched_at",
            ),
            transform=self._transform_event_row,
            conflict_columns=("batch_date", "source_name", "title", "url"),
            update_columns=(
                "company_name",
                "source_type",
                "event_types_json",
                "tech_signals_json",
                "matched_companies_json",
                "matched_focus_keywords_json",
                "is_duplicate",
                "published_at",
                "fetched_at",
            ),
        )

    def sync_events_batch(self, directory: Path, batch_key: str) -> int:
        return self._sync_jsonl_file(
            file_path=directory / f"{batch_key}.jsonl",
            batch_date=batch_key,
            table_name="events",
            columns=(
                "batch_date",
                "company_name",
                "source_name",
                "source_type",
                "url",
                "title",
                "event_types_json",
                "tech_signals_json",
                "matched_companies_json",
                "matched_focus_keywords_json",
                "is_duplicate",
                "published_at",
                "fetched_at",
            ),
            transform=self._transform_event_row,
            conflict_columns=("batch_date", "source_name", "title", "url"),
            update_columns=(
                "company_name",
                "source_type",
                "event_types_json",
                "tech_signals_json",
                "matched_companies_json",
                "matched_focus_keywords_json",
                "is_duplicate",
                "published_at",
                "fetched_at",
            ),
        )

    def sync_change_logs(self, directory: Path) -> int:
        return self._sync_jsonl_directory(
            directory=directory,
            table_name="change_logs",
            columns=(
                "batch_date",
                "company_name",
                "source_name",
                "change_type",
                "target_type",
                "title",
                "summary",
                "detected_at",
                "importance_score",
                "url",
                "before_value",
                "after_value",
                "changed_ratio",
                "metadata_json",
            ),
            transform=self._transform_change_row,
            conflict_columns=("batch_date", "change_type", "source_name", "title", "url"),
            update_columns=(
                "company_name",
                "target_type",
                "summary",
                "detected_at",
                "importance_score",
                "before_value",
                "after_value",
                "changed_ratio",
                "metadata_json",
            ),
        )

    def sync_change_logs_batch(self, directory: Path, batch_key: str) -> int:
        return self._sync_jsonl_file(
            file_path=directory / f"{batch_key}.jsonl",
            batch_date=batch_key,
            table_name="change_logs",
            columns=(
                "batch_date",
                "company_name",
                "source_name",
                "change_type",
                "target_type",
                "title",
                "summary",
                "detected_at",
                "importance_score",
                "url",
                "before_value",
                "after_value",
                "changed_ratio",
                "metadata_json",
            ),
            transform=self._transform_change_row,
            conflict_columns=("batch_date", "change_type", "source_name", "title", "url"),
            update_columns=(
                "company_name",
                "target_type",
                "summary",
                "detected_at",
                "importance_score",
                "before_value",
                "after_value",
                "changed_ratio",
                "metadata_json",
            ),
        )

    def sync_insight_items(self, directory: Path) -> int:
        return self._sync_jsonl_directory(
            directory=directory,
            table_name="insight_items",
            columns=(
                "batch_date",
                "company_name",
                "source_name",
                "change_type",
                "target_type",
                "title",
                "summary",
                "importance_score",
                "reason",
                "detected_at",
                "priority_label",
                "url",
                "metadata_json",
            ),
            transform=self._transform_insight_row,
            conflict_columns=("batch_date", "change_type", "source_name", "title", "url"),
            update_columns=(
                "company_name",
                "target_type",
                "summary",
                "importance_score",
                "reason",
                "detected_at",
                "priority_label",
                "metadata_json",
            ),
        )

    def sync_insight_items_batch(self, directory: Path, batch_key: str) -> int:
        return self._sync_jsonl_file(
            file_path=directory / f"{batch_key}.jsonl",
            batch_date=batch_key,
            table_name="insight_items",
            columns=(
                "batch_date",
                "company_name",
                "source_name",
                "change_type",
                "target_type",
                "title",
                "summary",
                "importance_score",
                "reason",
                "detected_at",
                "priority_label",
                "url",
                "metadata_json",
            ),
            transform=self._transform_insight_row,
            conflict_columns=("batch_date", "change_type", "source_name", "title", "url"),
            update_columns=(
                "company_name",
                "target_type",
                "summary",
                "importance_score",
                "reason",
                "detected_at",
                "priority_label",
                "metadata_json",
            ),
        )

    def upsert_task_run(
        self,
        batch_key: str,
        stage_name: str,
        status: str,
        started_at: str | None = None,
        finished_at: str | None = None,
        message: str | None = None,
        error_text: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO task_runs (
                    batch_key, stage_name, status, started_at, finished_at,
                    message, error_text, metadata_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(batch_key, stage_name) DO UPDATE SET
                    status=excluded.status,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    message=excluded.message,
                    error_text=excluded.error_text,
                    metadata_json=excluded.metadata_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    batch_key,
                    stage_name,
                    status,
                    started_at,
                    finished_at,
                    message,
                    error_text,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

    def fetch_completed_batch_keys(
        self,
        stage_name: str,
        statuses: tuple[str, ...] = ("completed", "completed_with_errors"),
    ) -> list[str]:
        placeholders = ", ".join("?" for _ in statuses)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT batch_key
                FROM task_runs
                WHERE stage_name = ?
                  AND status IN ({placeholders})
                ORDER BY batch_key
                """,
                (stage_name, *statuses),
            ).fetchall()
        return [row["batch_key"] for row in rows]

    def fetch_recent_task_runs(self, limit: int = 50) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT batch_key, stage_name, status, started_at, finished_at,
                       message, error_text, metadata_json
                FROM task_runs
                ORDER BY COALESCE(finished_at, started_at) DESC, batch_key DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def fetch_daily_insights(self, report_date: date, limit: int = 20) -> list[dict]:
        date_prefix = report_date.isoformat()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT batch_date, company_name, source_name, change_type, target_type,
                       title, summary, importance_score, reason, detected_at,
                       priority_label, url, metadata_json
                FROM insight_items
                WHERE batch_date LIKE ?
                  AND company_name IN (SELECT company_name FROM companies)
                ORDER BY importance_score DESC, detected_at DESC
                LIMIT ?
                """,
                (f"{date_prefix}%", limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_companies(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT company_name
                FROM companies
                ORDER BY company_name
                """
            ).fetchall()
        return [row["company_name"] for row in rows]

    def fetch_recent_events(
        self,
        company_name: str | None = None,
        date_prefix: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = """
            SELECT batch_date, company_name, source_name, source_type, url, title,
                   event_types_json, tech_signals_json, matched_companies_json,
                   matched_focus_keywords_json, is_duplicate, published_at, fetched_at
            FROM events
            WHERE company_name IN (SELECT company_name FROM companies)
        """
        params: list[object] = []
        if company_name and company_name != "All":
            query += " AND company_name = ?"
            params.append(company_name)
        if date_prefix:
            query += " AND batch_date LIKE ?"
            params.append(f"{date_prefix}%")
        query += " ORDER BY fetched_at DESC, batch_date DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def purge_non_message_events(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM events
                WHERE source_type != 'rss'
                   OR company_name IN ('行业通用', '琛屼笟閫氱敤')
                   OR lower(COALESCE(title, '')) LIKE '%snapshot%'
                   OR source_name IN ('官网首页', '关于我们页', '招聘页', '职位页', '投资者关系页')
                """
            )
        return cursor.rowcount

    def fetch_recent_changes(
        self,
        company_name: str | None = None,
        date_prefix: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = """
            SELECT batch_date, company_name, source_name, change_type, target_type,
                   title, summary, detected_at, importance_score, url,
                   before_value, after_value, changed_ratio, metadata_json
            FROM change_logs
            WHERE company_name IN (SELECT company_name FROM companies)
        """
        params: list[object] = []
        if company_name and company_name != "All":
            query += " AND company_name = ?"
            params.append(company_name)
        if date_prefix:
            query += " AND batch_date LIKE ?"
            params.append(f"{date_prefix}%")
        query += " ORDER BY detected_at DESC, importance_score DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def fetch_recent_insights(
        self,
        company_name: str | None = None,
        date_prefix: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = """
            SELECT batch_date, company_name, source_name, change_type, target_type,
                   title, summary, importance_score, reason, detected_at,
                   priority_label, url, metadata_json
            FROM insight_items
            WHERE company_name IN (SELECT company_name FROM companies)
        """
        params: list[object] = []
        if company_name and company_name != "All":
            query += " AND company_name = ?"
            params.append(company_name)
        if date_prefix:
            query += " AND batch_date LIKE ?"
            params.append(f"{date_prefix}%")
        query += " ORDER BY importance_score DESC, detected_at DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def fetch_daily_changes(self, report_date: date, limit: int = 20) -> list[dict]:
        date_prefix = report_date.isoformat()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT batch_date, company_name, source_name, change_type, target_type,
                       title, summary, detected_at, importance_score, url,
                       before_value, after_value, changed_ratio, metadata_json
                FROM change_logs
                WHERE batch_date LIKE ?
                  AND company_name IN (SELECT company_name FROM companies)
                ORDER BY importance_score DESC, detected_at DESC
                LIMIT ?
                """,
                (f"{date_prefix}%", limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def fetch_daily_events(self, report_date: date, limit: int = 20) -> list[dict]:
        date_prefix = report_date.isoformat()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT batch_date, company_name, source_name, source_type, url, title,
                       event_types_json, tech_signals_json, matched_companies_json,
                       matched_focus_keywords_json, is_duplicate, published_at, fetched_at
                FROM events
                WHERE batch_date LIKE ?
                  AND company_name IN (SELECT company_name FROM companies)
                ORDER BY fetched_at DESC, title ASC
                LIMIT ?
                """,
                (f"{date_prefix}%", limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def fetch_daily_counts(self, report_date: date) -> dict[str, int]:
        date_prefix = report_date.isoformat()
        with self.connect() as connection:
            counts = {}
            for table_name in ("events", "change_logs", "insight_items"):
                counts[table_name] = connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {table_name}
                    WHERE batch_date LIKE ?
                      AND company_name IN (SELECT company_name FROM companies)
                    """,
                    (f"{date_prefix}%",),
                ).fetchone()[0]
        return counts

    def upsert_report_run(
        self,
        report_date: date,
        report_type: str,
        status: str,
        output_path: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO report_runs (report_date, report_type, status, output_path, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(report_date) DO UPDATE SET
                    report_type=excluded.report_type,
                    status=excluded.status,
                    output_path=excluded.output_path,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (report_date.isoformat(), report_type, status, output_path),
            )

    def _sync_jsonl_directory(
        self,
        directory: Path,
        table_name: str,
        columns: tuple[str, ...],
        transform,
        conflict_columns: tuple[str, ...],
        update_columns: tuple[str, ...],
    ) -> int:
        rows = []
        for file_path in sorted(directory.glob("*.jsonl")) if directory.exists() else []:
            batch_date = file_path.stem
            rows.extend(transform(batch_date, self._read_jsonl(file_path)))

        if not rows:
            return 0

        placeholders = ", ".join(f":{column}" for column in columns)
        insert_columns = ", ".join(columns)
        conflict_clause = ", ".join(conflict_columns)
        update_clause = ", ".join(
            f"{column}=excluded.{column}" for column in update_columns
        )

        with self.connect() as connection:
            connection.executemany(
                f"""
                INSERT INTO {table_name} ({insert_columns}, updated_at)
                VALUES ({placeholders}, CURRENT_TIMESTAMP)
                ON CONFLICT({conflict_clause}) DO UPDATE SET
                    {update_clause},
                    updated_at=CURRENT_TIMESTAMP;
                """,
                rows,
            )

        return len(rows)

    def _sync_jsonl_file(
        self,
        file_path: Path,
        batch_date: str,
        table_name: str,
        columns: tuple[str, ...],
        transform,
        conflict_columns: tuple[str, ...],
        update_columns: tuple[str, ...],
    ) -> int:
        if not file_path.exists():
            return 0

        rows = transform(batch_date, self._read_jsonl(file_path))
        if not rows:
            return 0

        placeholders = ", ".join(f":{column}" for column in columns)
        insert_columns = ", ".join(columns)
        conflict_clause = ", ".join(conflict_columns)
        update_clause = ", ".join(
            f"{column}=excluded.{column}" for column in update_columns
        )

        with self.connect() as connection:
            connection.executemany(
                f"""
                INSERT INTO {table_name} ({insert_columns}, updated_at)
                VALUES ({placeholders}, CURRENT_TIMESTAMP)
                ON CONFLICT({conflict_clause}) DO UPDATE SET
                    {update_clause},
                    updated_at=CURRENT_TIMESTAMP;
                """,
                rows,
            )

        return len(rows)

    @staticmethod
    def _read_jsonl(file_path: Path) -> list[dict]:
        rows = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        payload = dict(row)
        for json_column in (
            "event_types_json",
            "tech_signals_json",
            "matched_companies_json",
            "matched_focus_keywords_json",
            "metadata_json",
        ):
            if json_column in payload and payload[json_column]:
                payload[json_column] = json.loads(payload[json_column])
        return payload

    @staticmethod
    def _transform_event_row(batch_date: str, rows: Iterable[dict]) -> list[dict]:
        transformed = []
        for row in rows:
            resolved_company_name = BusinessDatabase._resolve_company_name(
                row.get("company_name", ""),
                row.get("matched_companies", []),
            )
            if not resolved_company_name:
                continue
            transformed.append(
                {
                    "batch_date": batch_date,
                    "company_name": resolved_company_name,
                    "source_name": row.get("source_name", ""),
                    "source_type": row.get("source_type", ""),
                    "url": row.get("url", ""),
                    "title": row.get("title", ""),
                    "event_types_json": json.dumps(row.get("event_types", []), ensure_ascii=False),
                    "tech_signals_json": json.dumps(row.get("tech_signals", []), ensure_ascii=False),
                    "matched_companies_json": json.dumps(row.get("matched_companies", []), ensure_ascii=False),
                    "matched_focus_keywords_json": json.dumps(row.get("matched_focus_keywords", []), ensure_ascii=False),
                    "is_duplicate": 1 if row.get("is_duplicate") else 0,
                    "published_at": row.get("published_at"),
                    "fetched_at": row.get("fetched_at"),
                }
            )
        return transformed

    @staticmethod
    def _transform_change_row(batch_date: str, rows: Iterable[dict]) -> list[dict]:
        transformed = []
        for row in rows:
            metadata = row.get("metadata", {})
            resolved_company_name = BusinessDatabase._resolve_company_name(
                row.get("company_name", ""),
                metadata.get("matched_companies", []),
            )
            if not resolved_company_name:
                continue
            transformed.append(
                {
                    "batch_date": batch_date,
                    "company_name": resolved_company_name,
                    "source_name": row.get("source_name", ""),
                    "change_type": row.get("change_type", ""),
                    "target_type": row.get("target_type", ""),
                    "title": row.get("title", ""),
                    "summary": row.get("summary", ""),
                    "detected_at": row.get("detected_at"),
                    "importance_score": row.get("importance_score"),
                    "url": row.get("url", ""),
                    "before_value": row.get("before_value"),
                    "after_value": row.get("after_value"),
                    "changed_ratio": row.get("changed_ratio"),
                    "metadata_json": json.dumps(metadata, ensure_ascii=False),
                }
            )
        return transformed

    @staticmethod
    def _transform_insight_row(batch_date: str, rows: Iterable[dict]) -> list[dict]:
        transformed = []
        for row in rows:
            metadata = row.get("metadata", {})
            resolved_company_name = BusinessDatabase._resolve_company_name(
                row.get("company_name", ""),
                metadata.get("matched_companies", []),
            )
            if not resolved_company_name:
                continue
            transformed.append(
                {
                    "batch_date": batch_date,
                    "company_name": resolved_company_name,
                    "source_name": row.get("source_name", ""),
                    "change_type": row.get("change_type", ""),
                    "target_type": row.get("target_type", ""),
                    "title": row.get("title", ""),
                    "summary": row.get("summary", ""),
                    "importance_score": row.get("importance_score"),
                    "reason": row.get("reason", ""),
                    "detected_at": row.get("detected_at"),
                    "priority_label": row.get("priority_label", ""),
                    "url": row.get("url", ""),
                    "metadata_json": json.dumps(metadata, ensure_ascii=False),
                }
            )
        return transformed

    @staticmethod
    def _resolve_company_name(company_name: str, matched_companies: list[str]) -> str:
        filtered = [item for item in matched_companies if item and item != "行业通用"]
        if filtered:
            return ", ".join(filtered)
        if company_name == "行业通用":
            return ""
        return company_name
