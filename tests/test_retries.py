import pytest

from task_runner.retry import backoff_delay


@pytest.mark.parametrize(
    ("attempts", "expected"),
    [
        (1, 2),
        (2, 4),
        (3, 8),
        (10, 60),
    ],
)
def test_backoff_delay(attempts: int, expected: float) -> None:
    assert backoff_delay(attempts) == expected

@pytest.mark.parametrize("bad", [0, -1])
def test_backoff_delay_rejects_bad_attempts(bad: int) -> None:
    with pytest.raises(ValueError):
        backoff_delay(bad)

