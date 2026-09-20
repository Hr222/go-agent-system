from __future__ import annotations

import ast
import importlib
from pathlib import Path

TASK_ROOT = Path("app/platform/task")
FORBIDDEN_IMPORT_PREFIXES = (
    "fastapi",
    "sqlalchemy",
    "app.business",
    "app.infrastructure",
    "app.interfaces",
)


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_task_domain_and_ports_do_not_depend_on_protocol_or_infrastructure_layers() -> None:
    source_files = [
        *TASK_ROOT.joinpath("domain").glob("*.py"),
        *TASK_ROOT.joinpath("ports").glob("*.py"),
    ]

    for path in source_files:
        for imported in _imports_from(path):
            assert not imported.startswith(FORBIDDEN_IMPORT_PREFIXES), (
                f"{path} 不能依赖协议、基础设施或具体业务层：{imported}"
            )


def test_task_application_does_not_depend_on_protocol_or_persistence_adapters() -> None:
    source_files = TASK_ROOT.joinpath("application").glob("*.py")

    for path in source_files:
        for imported in _imports_from(path):
            assert not imported.startswith(FORBIDDEN_IMPORT_PREFIXES), (
                f"{path} 不能依赖协议或持久化适配器：{imported}"
            )


def test_trusted_submission_is_the_only_new_task_creation_boundary() -> None:
    application_source = TASK_ROOT.joinpath("application", "trusted_submission.py").read_text(
        encoding="utf-8"
    )
    composition_source = Path("app/composition/task.py").read_text(encoding="utf-8")

    assert "class TrustedTaskSubmissionService" in application_source
    assert "def build_trusted_task_submission_service" in composition_source


def test_task_runtime_excludes_test_repository_and_executor_lease_exports() -> None:
    application_package = importlib.import_module("app.platform.task.application")

    assert not TASK_ROOT.joinpath("application", "in_memory_repository.py").exists()
    assert not hasattr(application_package, "AttemptLease")
    assert not hasattr(application_package, "ClaimTaskCommand")
    assert not hasattr(application_package, "RenewLeaseCommand")


def test_task_worker_context_excludes_sensitive_input_fields() -> None:
    from dataclasses import fields

    from app.platform.task.ports.worker import TaskExecutionContext

    field_names = {field.name for field in fields(TaskExecutionContext)}
    assert "input_fingerprint" not in field_names
    assert "lease_token" not in field_names
    assert "owner_subject" in field_names
    assert "renew_lease" in field_names


def test_task_worker_ports_do_not_depend_on_protocol_or_infrastructure_layers() -> None:
    worker_port = TASK_ROOT.joinpath("ports", "worker.py")
    for imported in _imports_from(worker_port):
        assert not imported.startswith(FORBIDDEN_IMPORT_PREFIXES), (
            f"{worker_port} 不能依赖协议、基础设施或具体业务层：{imported}"
        )


def test_task_composition_exposes_only_fixed_worker_binding() -> None:
    composition_source = Path("app/composition/task.py").read_text(encoding="utf-8")

    assert "def build_task_worker" in composition_source
    assert "MappingTaskExecutorRegistry" in composition_source
    assert "register" not in composition_source


def test_task_recovery_schedulers_use_application_and_ports_only() -> None:
    recovery_source = TASK_ROOT.joinpath("application", "recovery.py")
    for imported in _imports_from(recovery_source):
        assert not imported.startswith(
            ("sqlalchemy", "app.infrastructure", "app.interfaces", "fastapi")
        ), f"{recovery_source} 不能直接依赖持久化、协议或 HTTP：{imported}"

    source = recovery_source.read_text(encoding="utf-8")
    assert "TaskLifecycleService" in source
    assert "TaskRepositoryPort" in source
    assert "Session" not in source
    assert "TaskRecord" not in source


def test_task_http_routes_use_application_dependencies_only() -> None:
    route_source = Path("app/interfaces/http/routes/tasks.py").read_text(encoding="utf-8")
    schema_source = Path("app/interfaces/http/schemas/task.py").read_text(encoding="utf-8")

    assert "OwnedTaskApplication" in route_source
    assert "get_owned_task_application" in route_source
    assert "Session" not in route_source
    assert "TaskRecord" not in route_source
    assert "lease_token" not in schema_source
    assert "input_fingerprint" not in schema_source


def test_agent_task_bridge_uses_trusted_submission_without_task_repository() -> None:
    bridge_source = Path(
        "app/platform/interaction/application/agent_task_bridge.py"
    ).read_text(encoding="utf-8")
    port_source = Path(
        "app/platform/interaction/ports/agent_task_bridge.py"
    ).read_text(encoding="utf-8")

    assert "TaskRepositoryPort" not in bridge_source
    assert "TaskLifecycleService" not in bridge_source
    assert "PostgresTaskRepository" not in bridge_source
    assert "TrustedTaskSubmissionCommand" in bridge_source
    assert "TaskRepositoryPort" not in port_source
    assert "TaskLifecycleService" not in port_source


def test_agent_protocol_and_business_agent_do_not_import_task_write_internals() -> None:
    forbidden_prefixes = (
        "app.platform.task.ports.repository",
        "app.platform.task.application.lifecycle_service",
    )
    source_files = [
        *Path("app/interfaces/agent").rglob("*.py"),
        *Path("app/business/agents").rglob("*.py"),
        Path("app/platform/interaction/application/agent_execution.py"),
    ]

    for path in source_files:
        for imported in _imports_from(path):
            assert not imported.startswith(forbidden_prefixes), (
                f"{path} 不能直接依赖 Task Repository 或生命周期服务：{imported}"
            )


def test_task_http_has_no_generic_task_creation_route() -> None:
    route_source = Path("app/interfaces/http/routes/tasks.py").read_text(encoding="utf-8")
    assert '"/tasks"' not in route_source
    assert '@router.post("/{task_id}/cancel"' in route_source
    assert '@router.post("/{task_id}/retry"' in route_source
    assert 'def create_task' not in route_source
