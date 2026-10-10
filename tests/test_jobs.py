from pathlib import Path

import pytest

from task_runner.database import initialize_database
from task_runner.jobs import get_job, submit_job


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
