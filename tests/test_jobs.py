import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from task_runner.database import get_connection, initialize_database
from task_runner.jobs import claim_job, get_job, submit_job


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    initialize_database(path)
    return path


def test_submit_and_retrieve_job(db_path: Path) -> None:
    job_id = submit_job("generate_report", {"report_id": 42}, db_path=db_path)

    job = get_job(job_id, db_path=db_path)

    assert job is not None
    assert job["id"] == job_id
    assert job["status"] == "pending"


def test_get_nonexistent_job(db_path: Path) -> None:
    assert get_job(-1, db_path=db_path) is None


def test_only_one_thread_claims_a_job(db_path: Path) -> None:
    submit_job("generate_report", {}, db_path=db_path)
    barrier = threading.Barrier(8)

    def attempt() -> dict | None:
        barrier.wait()  # release all 8 threads at the same instant
        return claim_job(db_path=db_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(attempt) for _ in range(8)]
        results = [f.result() for f in futures]

    winners = [r for r in results if r is not None]
    assert len(winners) == 1

def test_multiple_threads_claim_multiple_jobs(db_path: Path) -> None:
    for name in ["a", "b", "c", "d", "e", "f", "g", "h"]:
        submit_job(name, {}, db_path=db_path)

    barrier = threading.Barrier(8)

    def attempt() -> dict | None:
        barrier.wait()
        return claim_job(db_path=db_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(attempt) for _ in range(8)]
        results = [f.result() for f in futures]

    winners = [r for r in results if r is not None]
    assert len(winners) == 8
    assert len({w["id"] for w in winners}) == 8  # all different jobs


def test_skip_future_jobs(db_path: Path) -> None:
    job_id = submit_job("do later", {}, db_path=db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET run_at = datetime('now', '+1 hour') WHERE id = ?",
            (job_id,),
        )

    assert claim_job(db_path=db_path) is None