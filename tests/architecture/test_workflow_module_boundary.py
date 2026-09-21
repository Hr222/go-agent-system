from __future__ import annotations

from pathlib import Path

WORKFLOW_ROOT = Path("app/platform/workflow")


def test_workflow_domain_and_application_do_not_import_infrastructure_or_http() -> None:
    forbidden = ("sqlalchemy", "fastapi", "starlette")
    for path in WORKFLOW_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        if "domain" in path.parts or "application" in path.parts:
            imports = "\n".join(
                line for line in source.splitlines() if line.startswith(("import ", "from "))
            )
            assert not any(token in imports for token in forbidden), path


def test_workflow_has_no_public_route_registration() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in WORKFLOW_ROOT.rglob("*.py")
    ).lower()
    assert "@router" not in source
    assert "mcp" not in source
    assert "function calling" not in source
