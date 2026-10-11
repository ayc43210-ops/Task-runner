import pytest

from task_runner.states import TRANSITIONS, JobStatus, can_transition

TERMINAL = [JobStatus.COMPLETED, JobStatus.FAILED]


def test_every_status_has_a_transitions_entry() -> None:
    assert set(TRANSITIONS) == set(JobStatus)


@pytest.mark.parametrize("status", TERMINAL)
def test_terminal_states_have_no_exits(status: JobStatus) -> None:
    assert TRANSITIONS[status] == frozenset()


@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (JobStatus.PENDING, JobStatus.RUNNING),
        (JobStatus.RUNNING, JobStatus.COMPLETED),
        (JobStatus.RUNNING, JobStatus.PENDING),  # retry
        (JobStatus.RUNNING, JobStatus.FAILED),
    ],
)
def test_legal_transitions(src: JobStatus, dst: JobStatus) -> None:
    assert can_transition(src, dst)


@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (JobStatus.PENDING, JobStatus.COMPLETED),  # must pass through running
        (JobStatus.PENDING, JobStatus.FAILED),
        (JobStatus.COMPLETED, JobStatus.RUNNING),
        (JobStatus.FAILED, JobStatus.PENDING),
        (JobStatus.RUNNING, JobStatus.RUNNING),
    ],
)
def test_illegal_transitions(src: JobStatus, dst: JobStatus) -> None:
    assert not can_transition(src, dst)
