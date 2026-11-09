import pytest

from task_runner.handler import write_to_file_and_sleep
from task_runner.retry import PermanentError


def test_path_escape_is_rejected(tmp_path, monkeypatch):
    safe = tmp_path / "safe"
    safe.mkdir()
    monkeypatch.setenv("DEMO_DIR", str(safe))

    with pytest.raises(PermanentError):
        write_to_file_and_sleep({"path": "../escape.txt", "line": "x"})

    assert not (tmp_path / "escape.txt").exists()