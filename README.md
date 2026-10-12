# Task Runner

A lightweight background job queue built to learn how systems like Celery,
RQ, and BullMQ work: persistent job state, atomic job claiming, retries,
and failure recovery.

**Status:** in progress (single worker, SQLite-backed).

## Development

    uv sync
    uv run pytest