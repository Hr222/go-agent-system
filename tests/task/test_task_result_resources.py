from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.platform.security import RequestPrincipal
from app.platform.task.application import SubmitTaskCommand, TaskLifecycleService, TaskResultResourceApplication, TaskResultResourcesQuery
from app.platform.task.application.executor_contracts import ClaimTaskCommand, CompleteTaskCommand
from app.platform.task.errors import TaskResultResourceUnavailableError
from app.platform.task.ports.result_resource import TaskResultResource
from tests.task.in_memory_repository import InMemoryTaskRepository


class Reader:
    def __init__(self, resources):
        self.resources = resources
        self.calls = []

    def list_resources(self, *, task_id, owner_subject, conversation_id):
        self.calls.append((task_id, owner_subject, conversation_id))
        return self.resources


def test_result_resources_require_success_and_use_trusted_conversation() -> None:
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository)
    task = lifecycle.submit(SubmitTaskCommand("owner-1", "tender.generate", "key-1", "input-1", 2, {"conversation_id": "conversation-1"}))
    claimed = lifecycle.claim(ClaimTaskCommand(task.id, "worker-1", "claim-1", "lease-1", datetime.now(timezone.utc) + timedelta(minutes=5)))
    lifecycle.complete(
        CompleteTaskCommand(
            task_id=task.id,
            attempt_id=claimed.lease.attempt_id,
            lease_token=claimed.lease.lease_token,
            result_fingerprint="fp-1",
            result_summary="done",
        )
    )
    resource = TaskResultResource("resource-1", "result.docx", "application/octet-stream", 4, "a" * 64)
    reader = Reader((resource,))
    application = TaskResultResourceApplication(repository, reader)

    result = application.list_owned(TaskResultResourcesQuery(RequestPrincipal("owner-1", authenticated=True), task.id))

    assert result.resources == (resource,)
    assert result.conversation_id == "conversation-1"
    assert reader.calls == [(task.id, "owner-1", "conversation-1")]


def test_result_resources_hide_unfinished_and_cross_subject_tasks() -> None:
    repository = InMemoryTaskRepository()
    lifecycle = TaskLifecycleService(repository)
    task = lifecycle.submit(SubmitTaskCommand("owner-1", "tender.generate", "key-1", "input-1", 2, {"conversation_id": "conversation-1"}))
    application = TaskResultResourceApplication(repository, Reader(()))

    with pytest.raises(TaskResultResourceUnavailableError):
        application.list_owned(TaskResultResourcesQuery(RequestPrincipal("owner-1", authenticated=True), task.id))
    with pytest.raises(TaskResultResourceUnavailableError):
        application.list_owned(TaskResultResourcesQuery(RequestPrincipal("owner-2", authenticated=True), task.id))
