from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app.platform.task.application import (
    MappingTaskExecutorRegistry,
    SecureLeaseIssuer,
    SubmitTaskCommand,
    TaskLifecycleService,
    TaskWorker,
    WorkerPollStatus,
)
from app.platform.task.domain import FailureCategory, TaskEventType, TaskStatus
from app.platform.task.errors import TaskLeaseRejectedError
from app.platform.task.ports.worker import (
    TaskExecutionContext,
    TaskExecutionFailure,
    TaskExecutionSuccess,
)
from tests.task.in_memory_repository import InMemoryTaskRepository


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class SuccessExecutor:
    def __init__(self) -> None:
        self.contexts: list[TaskExecutionContext] = []

    def execute(self, context: TaskExecutionContext) -> TaskExecutionSuccess:
        self.contexts.append(context)
        renewed = context.renew_lease()
        assert renewed.renewal_sequence == 1
        return TaskExecutionSuccess(
            result_fingerprint="result-sha-1",
            result_summary="合成执行完成",
        )


class FailureExecutor:
    def __init__(self, failure: TaskExecutionFailure) -> None:
        self.failure = failure

    def execute(self, context: TaskExecutionContext) -> TaskExecutionFailure:
        return self.failure


class RaisingExecutor:
    def execute(self, context: TaskExecutionContext) -> object:
        raise RuntimeError("provider response contains secret-token")


class RenewalExecutor:
    def execute(self, context: TaskExecutionContext) -> TaskExecutionSuccess:
        context.renew_lease()
        return TaskExecutionSuccess("renewed-result", "不应提交")


class RejectingRenewalIssuer(SecureLeaseIssuer):
    def renew(self, *, worker_id, now, current_expires_at):  # noqa: ANN001
        raise TaskLeaseRejectedError("lease 已失效")


def _submit(service: TaskLifecycleService, *, key: str = "submit-1"):
    return service.submit(
        SubmitTaskCommand(
            owner_subject="owner-1",
            task_type="demo.execute",
            idempotency_key=key,
            input_fingerprint="input-sha-1",
            max_attempts=2,
            display_metadata={"title": "合成任务"},
        )
    )


def _worker(
    repository: InMemoryTaskRepository,
    clock: MutableClock,
    executor: object,
    *,
    worker_id: str = "worker-1",
) -> TaskWorker:
    lifecycle = TaskLifecycleService(repository, clock=clock)
    return TaskWorker(
        repository=repository,
        lifecycle=lifecycle,
        executors=MappingTaskExecutorRegistry({"demo.execute": executor}),
        lease_issuer=SecureLeaseIssuer(
            ttl=timedelta(minutes=5),
            token_factory=lambda: "worker-lease-token",
        ),
        worker_id=worker_id,
        clock=clock,
    )


def test_worker_polls_and_completes_task_without_exposing_input() -> None:
    repository = InMemoryTaskRepository()
    clock = MutableClock()
    executor = SuccessExecutor()
    service = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(service)

    result = _worker(repository, clock, executor).poll_once()

    assert result.status is WorkerPollStatus.SUCCEEDED
    assert result.task is not None
    assert result.task.status is TaskStatus.SUCCEEDED
    assert len(executor.contexts) == 1
    context = executor.contexts[0]
    assert context.task_id == submitted.id
    assert context.display_metadata == {"title": "合成任务"}
    assert context.lease.lease_token == "worker-lease-token"
    assert not hasattr(context, "input_fingerprint")
    task = repository.get(submitted.id)
    assert task is not None
    assert [event.event_type for event in task.events] == [
        TaskEventType.TASK_CREATED,
        TaskEventType.TASK_CLAIMED,
        TaskEventType.TASK_SUCCEEDED,
    ]


def test_worker_idle_poll_does_not_create_lifecycle_facts() -> None:
    repository = InMemoryTaskRepository()
    clock = MutableClock()

    result = _worker(repository, clock, SuccessExecutor()).poll_once()

    assert result.status is WorkerPollStatus.IDLE
    assert result.task is None
    assert repository._tasks == {}


def test_worker_unknown_executor_fails_task_with_safe_code() -> None:
    repository = InMemoryTaskRepository()
    clock = MutableClock()
    service = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(service)
    worker = TaskWorker(
        repository=repository,
        lifecycle=service,
        executors=MappingTaskExecutorRegistry({}),
        lease_issuer=SecureLeaseIssuer(token_factory=lambda: "worker-lease-token"),
        worker_id="worker-1",
        clock=clock,
    )

    result = worker.poll_once()

    assert result.status is WorkerPollStatus.FAILED
    assert result.task is not None
    assert result.task.status is TaskStatus.FAILED
    task = repository.get(submitted.id)
    assert task is not None
    assert task.failure_code == "EXECUTOR_UNAVAILABLE"


def test_worker_converts_executor_exception_to_safe_failure() -> None:
    repository = InMemoryTaskRepository()
    clock = MutableClock()
    service = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(service)

    result = _worker(repository, clock, RaisingExecutor()).poll_once()

    assert result.status is WorkerPollStatus.FAILED
    task = repository.get(submitted.id)
    assert task is not None
    assert task.failure_code == "EXECUTOR_FAILED"
    assert all("secret-token" not in repr(event.metadata) for event in task.events)


def test_worker_stops_result_write_when_lease_renewal_is_rejected() -> None:
    repository = InMemoryTaskRepository()
    clock = MutableClock()
    service = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(service)
    worker = TaskWorker(
        repository=repository,
        lifecycle=service,
        executors=MappingTaskExecutorRegistry({"demo.execute": RenewalExecutor()}),
        lease_issuer=RejectingRenewalIssuer(token_factory=lambda: "worker-lease-token"),
        worker_id="worker-1",
        clock=clock,
    )

    result = worker.poll_once()

    assert result.status is WorkerPollStatus.REJECTED
    assert result.error_code == "LEASE_REJECTED"
    task = repository.get(submitted.id)
    assert task is not None
    assert task.status is TaskStatus.RUNNING


def test_worker_preserves_existing_retry_policy_for_transient_failure() -> None:
    repository = InMemoryTaskRepository()
    clock = MutableClock()
    service = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(service)
    failure = TaskExecutionFailure(
        failure_category=FailureCategory.TRANSIENT,
        failure_code="TEMPORARY_PROVIDER",
        result_fingerprint="failure-sha-1",
        retry_at=clock.now + timedelta(minutes=1),
    )

    result = _worker(repository, clock, FailureExecutor(failure)).poll_once()

    assert result.status is WorkerPollStatus.FAILED
    assert result.task is not None
    assert result.task.status is TaskStatus.RETRY_WAIT
    task = repository.get(submitted.id)
    assert task is not None
    assert task.attempts[0].failure_category is FailureCategory.TRANSIENT


def test_concurrent_workers_claim_at_most_one_task() -> None:
    repository = InMemoryTaskRepository()
    clock = MutableClock()
    service = TaskLifecycleService(repository, clock=clock)
    submitted = _submit(service)
    executor = SuccessExecutor()

    def poll(worker_id: str):
        return _worker(repository, clock, executor, worker_id=worker_id).poll_once()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(poll, ["worker-1", "worker-2"]))

    assert sorted(result.status.value for result in results) == ["idle", "succeeded"]
    task = repository.get(submitted.id)
    assert task is not None
    assert len(task.attempts) == 1
    assert [event.event_type for event in task.events].count(TaskEventType.TASK_CLAIMED) == 1
