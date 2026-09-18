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


def test_task_runtime_excludes_test_repository_and_executor_lease_exports() -> None:
    application_package = importlib.import_module("app.platform.task.application")

    assert not TASK_ROOT.joinpath("application", "in_memory_repository.py").exists()
    assert not hasattr(application_package, "AttemptLease")
    assert not hasattr(application_package, "ClaimTaskCommand")
    assert not hasattr(application_package, "RenewLeaseCommand")
