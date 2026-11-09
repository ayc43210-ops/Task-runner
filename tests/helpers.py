import time
from pathlib import Path
from collections.abc import Callable
from task_runner.database import get_connection


def wait_until(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met before timeout")

def count_jobs(db_path: Path) -> int:
    with get_connection(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
