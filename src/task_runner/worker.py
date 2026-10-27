import argparse
import json
import logging
import signal
import threading
import time
from collections.abc import Mapping
from pathlib import Path

from task_runner.handler import REGISTRY, Handler
from task_runner.jobs import (
    DB_PATH,
    claim_job,
    mark_completed,
    mark_failed,
    mark_retry,
    recover_expired_leases,
    renew_lease,
)
from task_runner.retry import MAX_ATTEMPTS, PermanentError, backoff_delay

logger = logging.getLogger(__name__)

def run_heartbeat(
    job_id: int,
    attempts: int,
    stop: threading.Event,
    interval: float,
    lease_seconds: float,
    db_path: Path = DB_PATH,
) -> None:
    while not stop.wait(interval):
        try:
            ok = renew_lease(job_id, attempts, lease_seconds, db_path=db_path)
        except Exception:  # noqa: BLE001 - one failed beat must not end the heartbeat
            logger.exception("heartbeat failed for job %s; will try again", job_id)
            continue
        if not ok:
            logger.warning("job %s no longer running under this attempt; heartbeat stopping", job_id)
            return

import threading
# keep your other imports; add PermanentError and run_heartbeat is in this file

def process_one(
    registry: Mapping[str, Handler],
    db_path: Path = DB_PATH,
    lease_seconds: float = 30.0,
    heartbeat_interval: float | None = None,
) -> bool:
    """Claim and run one job. Returns False if the queue was empty."""
    job = claim_job(db_path=db_path, lease_seconds=lease_seconds)
    if job is None:
        return False

    job_id, attempts = job["id"], job["attempts"]
    logger.info("Claimed job %s of type %s", job_id, job["type"])

    handler = registry.get(job["type"])
    if handler is None:
        mark_failed(job_id, attempts, f"UnknownJobType: {job['type']}", db_path)
        return True

    # Renew the lease about 3 times per lease period, so two missed beats in a row are still survivable.
    interval = heartbeat_interval if heartbeat_interval is not None else lease_seconds / 3
    hb_stop = threading.Event()
    hb = threading.Thread(
        target=run_heartbeat,
        args=(job_id, attempts, hb_stop, interval, lease_seconds, db_path),
        daemon=True,
    )
    hb.start()

    try:
        try:
            result = handler(json.loads(job["payload"]))
            try:
                result_json = json.dumps(result)
            except TypeError as exc:
                raise PermanentError(f"result is not JSON-serializable: {exc}") from exc
        finally:
            hb_stop.set()          # always stop the heartbeat first
            hb.join(timeout=5)
    except Exception as exc:  # noqa: BLE001 - handlers may raise anything; record and continue
        error = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, PermanentError) or attempts >= MAX_ATTEMPTS:
            mark_failed(job_id, attempts, error, db_path)
            logger.error("Job %s failed permanently: %s", job_id, error)
        else:
            delay = backoff_delay(attempts)
            mark_retry(job_id, attempts, error, delay, db_path)
            logger.warning(
                "Job %s failed (attempt %s of %s), retrying in %ss: %s",
                job_id, attempts, MAX_ATTEMPTS, delay, error,
            )
    else:
        mark_completed(job_id, attempts, result_json, db_path)
        logger.info("Job %s completed", job_id)

    return True

def run_worker(
        registry: Mapping[str,Handler],
        stop: threading.Event,
        db_path: Path = DB_PATH,
        poll_interval: float = 1.0,
        recovery_interval: float = 10.0,
        lease_seconds: float = 30.0,
        
    )->None:
       last_check = time.monotonic()
       while not stop.is_set():
        try:
            did_work = process_one(registry, db_path,lease_seconds)
            now = time.monotonic()
            if now - last_check >= recovery_interval:
                last_recovered = recover_expired_leases(MAX_ATTEMPTS,db_path)
                last_check = float("-inf")
                if last_recovered > 0:
                    logger.info("%s jobs recovered",last_recovered)
        except Exception:
            logger.exception("process_one crashed; backing off")
            did_work = False
        if not did_work:
            stop.wait(poll_interval)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    stop = threading.Event()
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll-interval",type = float,default=1.0)
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument("--lease-seconds", type=float, default=30.0)
    parser.add_argument("--recovery-interval", type=float, default=10.0)
    args = parser.parse_args()
    
    logger.info("worker started")

    def request_stop(signum: int, _: object) -> None:
        if stop.is_set():
            logger.warning("second signal received, exiting immediately")
            raise SystemExit(1)
        logger.info("received signal %s, finishing current job", signum)
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    run_worker(REGISTRY, stop, db_path=DB_PATH, poll_interval = args.poll_interval,recovery_interval=args.recovery_interval,lease_seconds=args.lease_seconds,)


if __name__ == "__main__":
    main()
