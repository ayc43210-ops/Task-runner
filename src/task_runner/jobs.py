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
            raise RuntimeError("Failed to retrieve the id of the submitted job")

    return job_id


def get_job(job_id: int, db_path: Path = DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    return dict(row) if row else None
