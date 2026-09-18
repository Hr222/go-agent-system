from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.platform.security.domain import RequestPrincipal
from app.platform.task.application import (
    TaskLifecycleService,
    TrustedTaskSubmissionCommand,
    TrustedTaskSubmissionProfile,
    TrustedTaskSubmissionService,
)
from app.platform.task.errors import (
    TaskSubmissionPolicyError,
    TaskSubmissionPrincipalError,
)
from tests.task.in_memory_repository import InMemoryTaskRepository


def _service(
    *,
    fields: tuple[str, ...] = ("title",),
) -> tuple[TrustedTaskSubmissionService, InMemoryTaskRepository]:
    repository = InMemoryTaskRepository()
    service = TrustedTaskSubmissionService(
        TaskLifecycleService(
            repository,
            clock=lambda: datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc),
        ),
        TrustedTaskSubmissionProfile(
            task_type="tender.generate",
            max_attempts=2,
            allow_manual_retry=False,
            display_metadata_fields=fields,
        ),
    )
    return service, repository


def test_trusted_submission_derives_owner_and_fixed_policy() -> None:
    service, repository = _service()

    view = service.submit(
        RequestPrincipal(subject="owner-1", authenticated=True),
        TrustedTaskSubmissionCommand(
            idempotency_key="submit-1",
            input_fingerprint="input-sha-1",
            display_metadata={"title": "合成任务"},
        ),
    )

    task = repository.get(view.id)
    assert task is not None
    assert task.owner_subject == "owner-1"
    assert task.task_type == "tender.generate"
    assert task.max_attempts == 2
    assert task.allow_manual_retry is False
    assert task.display_metadata == {"title": "合成任务"}


def test_trusted_submission_replay_returns_same_task_without_new_event() -> None:
    service, repository = _service()
    principal = RequestPrincipal(subject="owner-1", authenticated=True)
    command = TrustedTaskSubmissionCommand("submit-1", "input-sha-1", {"title": "任务"})

    first = service.submit(principal, command)
    replay = service.submit(principal, command)

    task = repository.get(first.id)
    assert replay.id == first.id
    assert task is not None
    assert len(task.events) == 1


@pytest.mark.parametrize(
    "principal",
    [
        RequestPrincipal.anonymous(),
        RequestPrincipal(subject="owner-1", authenticated=False),
        RequestPrincipal(subject="", authenticated=True),
    ],
)
def test_trusted_submission_rejects_untrusted_principal_without_side_effects(
    principal: RequestPrincipal,
) -> None:
    service, repository = _service()

    with pytest.raises(TaskSubmissionPrincipalError):
        service.submit(principal, TrustedTaskSubmissionCommand("submit-1", "input-sha-1"))

    assert repository._tasks == {}


def test_trusted_submission_rejects_unknown_display_field_without_side_effects() -> None:
    service, repository = _service()

    with pytest.raises(TaskSubmissionPolicyError):
        service.submit(
            RequestPrincipal(subject="owner-1", authenticated=True),
            TrustedTaskSubmissionCommand(
                "submit-1", "input-sha-1", {"unknown": "拒绝"}
            ),
        )

    assert repository._tasks == {}


def test_trusted_submission_rejects_non_string_display_value_without_side_effects() -> None:
    service, repository = _service()

    with pytest.raises(TaskSubmissionPolicyError):
        service.submit(
            RequestPrincipal(subject="owner-1", authenticated=True),
            TrustedTaskSubmissionCommand(
                "submit-1", "input-sha-1", {"title": 42},  # type: ignore[dict-item]
            ),
        )

    assert repository._tasks == {}


def test_profile_rejects_invalid_fixed_strategy() -> None:
    with pytest.raises(TaskSubmissionPolicyError):
        TrustedTaskSubmissionProfile(task_type="tender.generate", max_attempts=0)
