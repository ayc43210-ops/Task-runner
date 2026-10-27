import subprocess
import sys
from pathlib import Path

import pytest

from task_runner.database import initialize_database
from task_runner.jobs import get_job, submit_job
from tests.helpers import wait_until


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    initialize_database(path)
    return path


def test_crash_recovery(db_path:Path)->None:
    job_id = submit_job("sleep",{"seconds": 3},db_path)

    proc = subprocess.Popen(
        [sys.executable, "-m", "task_runner.worker",
        "--db-path", str(db_path),
        "--lease-seconds", "2",
        "--recovery-interval", "0.5",
        "--poll-interval", "0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def start()->bool:
        job = get_job(job_id,db_path)
        return job is not None and job["status"]=="running"
    
    def ended()->bool:
        job = get_job(job_id,db_path)
        return job is not None and job["status"]=="completed"
    
    try:
        wait_until(start)
    finally:
        proc.kill()
        proc.wait()
        proc2 = subprocess.Popen(
                [sys.executable, "-m", "task_runner.worker",
                "--db-path", str(db_path),
                "--lease-seconds", "2",
                "--recovery-interval", "0.5",
                "--poll-interval", "0.1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        try:
            
            wait_until(ended,timeout=15)
        finally:
            proc2.kill()
            proc2.wait()
    
    job  = get_job(job_id,db_path)
    assert job is not None
    assert job["status"]=="completed"
    assert job["attempts"] == 2
    
    assert job["last_error"] is None
    
    
