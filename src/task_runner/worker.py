import json
import time
import threading
from collections.abc import Mapping,Callable
from pathlib import Path


from task_runner.handler import Handler
from task_runner.jobs import DB_PATH, claim_job, mark_completed, mark_failed


def process_one(registry: Mapping[str, Handler], db_path: Path = DB_PATH) -> bool:
    """Claim and run one job. Returns False if the queue was empty."""
    job = claim_job(db_path=db_path)
    if job is None:
        return False

    job_id, attempts = job["id"], job["attempts"]

    handler = registry.get(job["type"])
    if handler is None:
        mark_failed(job_id, attempts, f"UnknownJobType: {job['type']}", db_path)
        return True

    try:
        result = handler(json.loads(job["payload"]))
        result_json = json.dumps(result)
    except Exception as exc:  # noqa: BLE001 - handlers may raise anything; record and continue
        mark_failed(job_id, attempts, f"{type(exc).__name__}: {exc}", db_path)
    else:
        mark_completed(job_id, attempts, result_json, db_path)

    return True

def run_worker(
        registry: Mapping[str,Handler],
        stop: threading.Event,
        db_path: Path = DB_PATH,
        poll_interval: float = 1.0,
    )->None:
        while not stop.is_set():
            did_work = process_one(registry,db_path)
            if not did_work:
                stop.wait(poll_interval)




def wait_until(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met before timeout")
