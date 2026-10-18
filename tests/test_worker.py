import json
import threading
from pathlib import Path

import pytest

from task_runner.database import get_connection, initialize_database
from task_runner.handler import Handler
from task_runner.jobs import claim_job, get_job, mark_completed, submit_job

from task_runner.worker import process_one, run_worker, wait_until


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    initialize_database(path)
    return path


def test_completed_job(db_path: Path) -> None:
    registry = {"ok": lambda payload: {"done": True}}
    job_id = submit_job("ok", {}, db_path)
    assert process_one(registry, db_path) is True
    job = get_job(job_id, db_path=db_path)

    assert job is not None
    assert job["status"] == "completed"

    assert json.loads(job["result"]) == {"done": True}
    assert job["last_error"] is None


def test_job_with_unknown_type(db_path: Path) -> None:
    registry = {"known": lambda payload: {"abcd": True}}
    job_id = submit_job("mystery", {}, db_path)
    assert process_one(registry, db_path) is True
    job = get_job(job_id, db_path=db_path)

    assert job is not None
    assert job["status"] == "failed"
    assert job["attempts"] == 1
    assert job["last_error"] == "UnknownJobType: mystery"
    assert job["result"] is None


def test_handler_fails(db_path: Path) -> None:
    def boom(payload: dict) -> dict:
        raise ValueError("bad input")

    registry = {"boom": boom}
    job_id = submit_job("boom", {}, db_path=db_path)

    assert process_one(registry, db_path=db_path) is True

    job = get_job(job_id, db_path=db_path)

    assert job is not None

    assert job["status"] == "pending"
    assert job["attempts"] == 1
    assert job["last_error"] == "ValueError: bad input"
    assert job["result"] is None


def test_empty_queue_returns_false(db_path: Path) -> None:
    assert process_one({}, db_path=db_path) is False
    assert claim_job(db_path=db_path) is None


def test_stale_worker_cannot_overwrite_result(db_path: Path) -> None:
    job_id = submit_job("ok", {}, db_path=db_path)
    job = claim_job(db_path=db_path)
    assert job is not None
    old_attempts = job["attempts"]  # worker A's attempt number

    # simulate: lease expired, job was handed to another worker (attempt 2)
    with get_connection(db_path) as conn:
        conn.execute("UPDATE jobs SET attempts = attempts + 1 WHERE id = ?", (job_id,))

    # worker A wakes up late and tries to record its result
    ok = mark_completed(job_id, old_attempts, json.dumps({"late": True}), db_path)

    assert ok is False
    after = get_job(job_id, db_path=db_path)
    assert after is not None
    assert after["status"] == "running"  # untouched
    assert after["result"] is None


def test_unserializable_result_marks_job_failed(db_path: Path) -> None:
    def bad(payload: dict) -> dict:
        return {1, 2, 3}  # pyright: ignore[reportReturnType]

    registry: dict[str, Handler] = {"bad": bad}
    job_id = submit_job("bad", {}, db_path=db_path)

    assert process_one(registry, db_path=db_path) is True

    job = get_job(job_id, db_path=db_path)
    assert job is not None
    assert job["status"] == "failed"
    assert job["last_error"] == "PermanentError: result is not JSON-serializable"


def test_worker_processes_jobs_then_stops(db_path):
    ids = [submit_job("ok", {}, db_path=db_path) for _ in range(3)]
    stop = threading.Event()
    t = threading.Thread(
        target=run_worker,
        args=({"ok": lambda p: {"done": True}}, stop, db_path, 0.05),
    )
    t.start()

    def all_completed() -> bool:
        return all(
            (job := get_job(i, db_path=db_path)) is not None
            and job["status"] == "completed"
            for i in ids
        )

    wait_until(all_completed)
    stop.set()
    t.join(timeout=5)
    assert not t.is_alive()

def test_worker_survives_unexpected_error( monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    calls: list[int] = []
    stop = threading.Event()

    def fake_process_one(registry: object, path: Path) -> bool:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database exploded")
        stop.set()  # second call: tell the loop to stop
        return False

    monkeypatch.setattr("task_runner.worker.process_one", fake_process_one)

    run_worker({}, stop, db_path=db_path, poll_interval=0.01)

    assert len(calls) == 2