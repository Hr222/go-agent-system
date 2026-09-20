from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.platform.security import RequestPrincipal
from app.platform.task.application import (
    TaskLifecycleService,
    TaskResultResource,
    TaskResultResourceApplication,
    TaskResultResourcesQuery,
)
from app.platform.task.application.contracts import SubmitTaskCommand
from app.platform.task.application.executor_contracts import (
    ClaimTaskCommand,
    CompleteTaskCommand,
)
from app.platform.task.errors import TaskResultResourceUnavailableError
from tests.task.in_memory_repository import InMemoryTaskRepository

_CONVERSATION_ID = "00000000-0000-0000-0000-000000000001"


class _ResourceReader:
    def __init__(self, resources: tuple[TaskResultResource, ...]) -> None:
        self.resources = resources
        self.calls: list[tuple[str, str]] = []

    def list_resources(self, *, task_id, owner_subject, conversation_id):  # noqa: ANN001
        del task_id
        self.calls.append((owner_subject, conversation_id))
        return self.resources


def _succeeded_task():  # noqa: ANN201 - test fixture keeps concrete Task incidental
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository)
    task = lifecycle.submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="tender.generate_bid_skeleton",
            idempotency_key="task-result-resources",
            input_fingerprint="input-fingerprint",
            max_attempts=2,
            display_metadata={"conversation_id": _CONVERSATION_ID},
        )
    )
    now = datetime.now(timezone.utc)
    claimed = lifecycle.claim(
        ClaimTaskCommand(
            task_id=task.id,
            worker_id="worker-1",
            claim_id="claim-1",
            lease_token="lease-1",
            lease_expires_at=now + timedelta(minutes=5),
        )
    )
    lifecycle.complete(
        CompleteTaskCommand(
            task_id=task.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            result_fingerprint="result-fingerprint",
            result_summary="Tender 投标骨架已生成。",
        )
    )
    return repository, task


def test_result_resource_application_requires_succeeded_owner_and_conversation() -> None:
    repository, task = _succeeded_task()
    resource = TaskResultResource(
        resource_id="a" * 32,
        file_name="bid.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=12,
        sha256="b" * 64,
    )
    reader = _ResourceReader((resource,))
    application = TaskResultResourceApplication(repository, reader)

    view = application.list_owned(
        TaskResultResourcesQuery(
            principal=RequestPrincipal(subject="owner-1", authenticated=True),
            task_id=task.id,
            conversation_id=_CONVERSATION_ID,
        )
    )

    assert view.resources == (resource,)
    assert reader.calls == [("owner-1", _CONVERSATION_ID)]
    for principal, conversation_id in (
        (RequestPrincipal(subject="other-owner", authenticated=True), _CONVERSATION_ID),
        (
            RequestPrincipal(subject="owner-1", authenticated=True),
            "00000000-0000-0000-0000-000000000002",
        ),
    ):
        with pytest.raises(TaskResultResourceUnavailableError):
            application.list_owned(
                TaskResultResourcesQuery(
                    principal=principal,
                    task_id=task.id,
                    conversation_id=conversation_id,
                )
            )


def test_result_resource_application_does_not_read_unfinished_task() -> None:
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository)
    task = lifecycle.submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="tender.generate_bid_skeleton",
            idempotency_key="unfinished-result-resources",
            input_fingerprint="input-fingerprint",
            max_attempts=2,
            display_metadata={"conversation_id": _CONVERSATION_ID},
        )
    )
    reader = _ResourceReader(())
    application = TaskResultResourceApplication(repository, reader)

    with pytest.raises(TaskResultResourceUnavailableError):
        application.list_owned(
            TaskResultResourcesQuery(
                principal=RequestPrincipal(subject="owner-1", authenticated=True),
                task_id=task.id,
                conversation_id=_CONVERSATION_ID,
            )
        )
    assert reader.calls == []
