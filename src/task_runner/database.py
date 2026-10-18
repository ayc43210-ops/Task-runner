import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "jobData.db"


@contextmanager
def get_connection(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # commits on success, rolls back on exception
            yield conn
    finally:
        conn.close()  # `with conn` alone does NOT do this


def initialize_database(db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
                result TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                attempts INTEGER NOT NULL DEFAULT 0,
                run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                lease_expires_at TEXT,
                last_error TEXT
            )
        """)
        
if __name__ == "__main__":
    initialize_database()