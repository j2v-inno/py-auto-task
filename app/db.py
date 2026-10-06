import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from .config import settings

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    import os

    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    with _lock, _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                receipt_handle TEXT,
                queue_url TEXT,
                received_at TEXT,
                receive_count INTEGER,
                deleted_from_sqs INTEGER DEFAULT 0,
                project_code TEXT,
                task_uid TEXT,
                file_id INTEGER,
                file_task_id INTEGER,
                payload TEXT
            )
            """
        )


def store_job(message: dict[str, Any], queue_url: str) -> int | None:
    """Store a raw SQS message. Returns new row id, or None if duplicate message_id."""
    body_raw = message.get("Body", "")
    try:
        payload = json.loads(body_raw)
    except (json.JSONDecodeError, TypeError):
        payload = {"_raw": body_raw}

    attrs = message.get("Attributes", {}) or {}
    with _lock, _conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO jobs (message_id, receipt_handle, queue_url, received_at,
                                  receive_count, project_code, task_uid, file_id,
                                  file_task_id, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.get("MessageId"),
                    message.get("ReceiptHandle"),
                    queue_url,
                    datetime.now(timezone.utc).isoformat(),
                    int(attrs.get("ApproximateReceiveCount", 0) or 0),
                    payload.get("project_code"),
                    payload.get("task_uid"),
                    payload.get("file_id"),
                    payload.get("file_task_id"),
                    json.dumps(payload),
                ),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def mark_deleted(message_id: str) -> None:
    with _lock, _conn() as conn:
        conn.execute("UPDATE jobs SET deleted_from_sqs = 1 WHERE message_id = ?", (message_id,))


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["payload"] = json.loads(d["payload"])
    except (json.JSONDecodeError, TypeError):
        pass
    d["deleted_from_sqs"] = bool(d["deleted_from_sqs"])
    return d


def list_jobs(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_job(job_id: int | None = None, file_task_id: int | None = None) -> dict[str, Any] | None:
    with _lock, _conn() as conn:
        if job_id is not None:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        elif file_task_id is not None:
            row = conn.execute(
                "SELECT * FROM jobs WHERE file_task_id = ? ORDER BY id DESC LIMIT 1",
                (file_task_id,),
            ).fetchone()
        else:
            return None
    return _row_to_dict(row) if row else None
