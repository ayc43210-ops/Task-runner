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
            raise RuntimeError(
                "Failed to retrieve the id of the submitted job"
            )  # pragm : no cover

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


def mark_completed(
    job_id: int, attempts: int, result_json: str, db_path: Path = DB_PATH
) -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'completed', result = ?, last_error = NULL,
                lease_expires_at = NULL
            WHERE id = ? AND status = 'running' AND attempts = ?
            """,
            (result_json, job_id, attempts),
        )
        return cursor.rowcount == 1


def mark_failed(
    job_id: int, attempts: int, error: str, db_path: Path = DB_PATH
) -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'failed', last_error = ?, lease_expires_at = NULL
            WHERE id = ? AND status = 'running' AND attempts = ?
            """,
            (error, job_id, attempts),
        )
        return cursor.rowcount == 1

def mark_retry(
    job_id: int,
    attempts: int,
    error: str,
    delay_seconds: float,
    db_path: Path = DB_PATH,
) -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'pending',
                run_at = datetime('now', ?),
                last_error = ?,
                lease_expires_at = NULL
            WHERE id = ? AND status = 'running' AND attempts = ?
            """,
            (f"+{delay_seconds} seconds", error, job_id, attempts),
        )
        return cursor.rowcount == 1

def recover_expired_leases(max_attempts: int,db_path: Path = DB_PATH)->int:
    with get_connection(db_path) as conn:

        cursor1 = conn.execute("""
            UPDATE jobs
            SET status = 'failed',
                last_error = 'LeaseExpired: worker did not finish in time',
                lease_expires_at = NULL
            WHERE status = 'running' AND lease_expires_at <= CURRENT_TIMESTAMP AND attempts >= ?
            """,
            (max_attempts,)
        )
        cursor2 = conn.execute("""
            UPDATE jobs
            SET status = 'pending',
                last_error = 'LeaseExpired: worker did not finish in time',
                run_at = CURRENT_TIMESTAMP,
                lease_expires_at = NULL
            WHERE status = 'running' AND lease_expires_at <= CURRENT_TIMESTAMP AND attempts <  ?
            """,
            (max_attempts,)
                )

        return cursor1.rowcount + cursor2.rowcount
    
