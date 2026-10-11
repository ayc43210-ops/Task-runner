import json
from pathlib import Path

from task_runner.database import DB_PATH, get_connection


def submit_job(job_type: str, payload: dict, db_path: Path = DB_PATH) -> int:
    payload_json = json.dumps(payload)

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO jobs (type, payload) VALUES (?, ?)",
            (job_type, payload_json),
        )
        job_id = cursor.lastrowid
        if job_id is None:
            raise RuntimeError("Failed to retrieve the id of the submitted job") # pragm : no cover

    return job_id


def get_job(job_id: int, db_path: Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    return dict(row) if row else None


def claim_job(db_path: Path = DB_PATH, lease_seconds: int = 30) -> dict | None:
    """Atomically claim the oldest eligible pending job, or return None."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                attempts = attempts + 1,
                lease_expires_at = datetime('now', ?)
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'pending' AND run_at <= CURRENT_TIMESTAMP
                ORDER BY run_at, id
                LIMIT 1
            )
            RETURNING *
            """,
            (f"+{lease_seconds} seconds",),
        ).fetchone()

    return dict(row) if row else None
