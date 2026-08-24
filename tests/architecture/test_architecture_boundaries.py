from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "app"


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    source_paths = [path] if path.is_file() else path.rglob("*.py")
    for source_path in source_paths:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


def _production_sources_outside_composition() -> list[Path]:
    return [
        source_path
        for source_path in APP_ROOT.rglob("*.py")
        if "infrastructure" not in source_path.parts
        and "composition" not in source_path.parts
    ]


def _called_class_names(path: Path) -> set[str]:
    names: set[str] = set()
    source_paths = [path] if path.is_file() else list(path.rglob("*.py"))
    for source_path in source_paths:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if isinstance(function, ast.Name):
                names.add(function.id)
            elif isinstance(function, ast.Attribute):
                names.add(function.attr)
    return names


def _literal_route_paths(path: Path) -> set[str]:
    """读取路由声明中的字面量路径，避免仅按文件名判断接口边界。"""

    route_paths: set[str] = set()
    for source_path in (path if path.is_dir() else path.parent).rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"get", "post", "put", "patch", "delete"}:
                continue
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(
                node.args[0].value, str
            ):
                route_paths.add(node.args[0].value)
    return route_paths


def test_ingestion_and_knowledge_do_not_depend_on_online_module() -> None:
    assert not any(
        module.startswith("app.modules.online")
        for module in _imported_modules(APP_ROOT / "modules" / "ingestion")
    )
    assert not any(
        module.startswith("app.modules.online")
        for module in _imported_modules(APP_ROOT / "modules" / "knowledge")
    )


def test_online_domain_does_not_depend_on_external_adapters() -> None:
    imported = _imported_modules(APP_ROOT / "modules" / "online" / "domain")
    forbidden_prefixes = (
        "app.infrastructure",
        "app.interfaces",
        "app.modules.knowledge",
        "app.modules.online.contracts",
        "langchain",
        "langgraph",
    )
    assert not any(
        module.startswith(forbidden)
        for module in imported
        for forbidden in forbidden_prefixes
    )


def test_http_schemas_do_not_reuse_ingestion_contracts() -> None:
    imported = _imported_modules(APP_ROOT / "interfaces" / "http" / "schemas")

    assert not any(
        module.startswith("app.modules.ingestion.contracts")
        for module in imported
    )


def test_http_interfaces_do_not_depend_on_infrastructure() -> None:
    imported = _imported_modules(APP_ROOT / "interfaces" / "http")

    assert not any(module.startswith("app.infrastructure") for module in imported)


def test_production_entrypoints_do_not_depend_on_infrastructure() -> None:
    imported: set[str] = set()
    for source_path in _production_sources_outside_composition():
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

    assert not any(module.startswith("app.infrastructure") for module in imported)


def test_concrete_adapters_are_instantiated_only_in_composition() -> None:
    forbidden_adapter_names = {
        "GiteeEmbeddingClient",
        "KnowledgePublicationRepository",
        "KnowledgeReadRepository",
        "KnowledgeWriteRepository",
        "LangChainGlmStructuredLlm",
        "LazyRagAnswerGenerator",
        "OpenAICompatibleClientFactory",
        "PolicyFileService",
        "PolicyOcrService",
        "PolicyPersistenceGateway",
        "PolicyUploadService",
        "RagAnswerGenerator",
        "SessionLocal",
    }

    for source_path in _production_sources_outside_composition():
        assert not (_called_class_names(source_path) & forbidden_adapter_names), (
            f"具体适配器不得在 Composition Root 外实例化：{source_path}"
        )

    assert _called_class_names(APP_ROOT / "composition") & forbidden_adapter_names


def test_all_domain_modules_do_not_depend_on_external_adapters() -> None:
    forbidden_prefixes = (
        "app.infrastructure",
        "app.interfaces",
        "fastapi",
        "sqlalchemy",
        "langchain",
        "langgraph",
    )
    domain_roots = (
        APP_ROOT / "modules" / "online" / "domain",
        APP_ROOT / "modules" / "knowledge" / "domain",
        APP_ROOT / "modules" / "ingestion" / "domain",
        APP_ROOT / "modules" / "agent" / "tender" / "domain",
        APP_ROOT / "modules" / "conversation" / "domain",
    )

    for domain_root in domain_roots:
        imported = _imported_modules(domain_root)
        assert not any(
            module.startswith(forbidden)
            for module in imported
            for forbidden in forbidden_prefixes
        ), f"Domain 不得依赖外部适配器：{domain_root}"


def test_conversation_domain_does_not_depend_on_llm_or_agent() -> None:
    imported = _imported_modules(APP_ROOT / "modules" / "conversation" / "domain")

    forbidden_prefixes = (
        "app.infrastructure",
        "app.interfaces",
        "app.modules.llm",
        "app.modules.agent",
        "fastapi",
        "sqlalchemy",
        "langchain",
        "langgraph",
    )
    assert not any(
        module.startswith(forbidden)
        for module in imported
        for forbidden in forbidden_prefixes
    )


def test_conversation_application_and_ports_do_not_depend_on_adapters() -> None:
    imported = _imported_modules(APP_ROOT / "modules" / "conversation" / "application")
    imported.update(_imported_modules(APP_ROOT / "modules" / "conversation" / "ports"))

    forbidden_prefixes = (
        "app.infrastructure",
        "app.interfaces",
        "app.modules.llm",
        "app.modules.agent",
        "fastapi",
        "sqlalchemy",
        "langchain",
        "langgraph",
    )
    assert not any(
        module.startswith(forbidden)
        for module in imported
        for forbidden in forbidden_prefixes
    )


def test_conversation_context_builder_is_independent_from_llm_and_persistence() -> None:
    imported = _imported_modules(
        APP_ROOT / "modules" / "conversation" / "domain" / "model_context.py"
    )
    imported.update(
        _imported_modules(
            APP_ROOT / "modules" / "conversation" / "application" / "context_builder.py"
        )
    )
    imported.update(
        _imported_modules(
            APP_ROOT / "modules" / "conversation" / "ports" / "context_cost_port.py"
        )
    )

    forbidden_prefixes = (
        "app.infrastructure",
        "app.interfaces",
        "app.modules.llm",
        "app.modules.agent",
        "fastapi",
        "sqlalchemy",
        "langchain",
        "langgraph",
    )
    assert not any(
        module.startswith(forbidden)
        for module in imported
        for forbidden in forbidden_prefixes
    )


def test_dialogue_runtime_depends_only_on_controlled_interaction_contracts() -> None:
    imported = _imported_modules(APP_ROOT / "modules" / "dialogue")

    forbidden_prefixes = (
        "app.infrastructure",
        "app.interfaces",
        "app.modules.agent",
        "app.modules.interaction.ports.agent_runtime",
        "app.modules.task",
        "fastapi",
        "sqlalchemy",
        "langchain",
        "langgraph",
    )
    assert not any(
        module.startswith(forbidden)
        for module in imported
        for forbidden in forbidden_prefixes
    )


def test_platform_capability_catalog_is_independent_of_dialogue_and_agent_runtime() -> None:
    catalog_roots = (
        APP_ROOT / "modules" / "interaction" / "domain" / "capability.py",
        APP_ROOT / "modules" / "interaction" / "ports" / "capability_catalog.py",
        APP_ROOT / "modules" / "interaction" / "application" / "catalog.py",
    )
    imported: set[str] = set()
    for catalog_root in catalog_roots:
        imported.update(_imported_modules(catalog_root))

    forbidden_prefixes = (
        "app.modules.dialogue",
        "app.modules.agent.runtime",
    )
    assert not any(
        module.startswith(forbidden)
        for module in imported
        for forbidden in forbidden_prefixes
    )


def test_dialogue_change_does_not_add_http_route() -> None:
    route_paths = _literal_route_paths(APP_ROOT / "interfaces" / "http" / "routes")

    assert not any("dialogue" in route_path.lower() for route_path in route_paths)


def test_conversation_http_routes_stay_in_the_interface_adapter() -> None:
    route_paths = _literal_route_paths(APP_ROOT / "interfaces" / "http" / "routes")

    assert "" in route_paths
    assert "/{conversation_id}/messages" in route_paths


def test_conversation_history_repository_is_read_only() -> None:
    source_path = (
        APP_ROOT
        / "infrastructure"
        / "persistence"
        / "repositories"
        / "conversation_history_read_repository.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    called_methods = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not called_methods & {"add", "commit", "delete", "flush", "execute"}
    assert "with_for_update" not in called_methods


def test_application_modules_do_not_depend_on_infrastructure() -> None:
    imported = _imported_modules(APP_ROOT / "modules")

    assert not any(module.startswith("app.infrastructure") for module in imported)


def test_module_ports_do_not_depend_on_infrastructure() -> None:
    imported: set[str] = set()
    for ports_root in (
        APP_ROOT / "modules" / "online" / "ports.py",
        APP_ROOT / "modules" / "ingestion" / "ports",
        APP_ROOT / "modules" / "knowledge" / "ports",
        APP_ROOT / "modules" / "agent" / "tender" / "ports",
    ):
        if ports_root.is_dir():
            imported.update(_imported_modules(ports_root))
        else:
            tree = ast.parse(ports_root.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)

    assert not any(
        module.startswith("app.infrastructure")
        for module in imported
    )


def test_http_ingestion_routes_use_application_use_cases() -> None:
    route_imports = _imported_modules(APP_ROOT / "interfaces" / "http" / "routes")

    assert "app.modules.ingestion.application.ingestion_use_case" in route_imports
    assert "app.interfaces.http.assemblers.policy_pipeline" in route_imports
    assert "app.interfaces.http.assemblers.policy_ingestion" in route_imports
    assert "app.interfaces.http.assemblers.publication" in route_imports
    assert not any(
        module.startswith("app.modules.ingestion.pipeline")
        for module in route_imports
    )


def test_tender_application_and_ports_do_not_depend_on_protocol_or_adapters() -> None:
    tender_root = APP_ROOT / "modules" / "agent" / "tender"
    imported = _imported_modules(tender_root)
    forbidden_prefixes = (
        "fastapi",
        "mcp",
        "app.infrastructure",
        "langchain",
        "langgraph",
        "python_docx",
    )
    assert not any(
        module.startswith(forbidden)
        for module in imported
        for forbidden in forbidden_prefixes
    )


def test_tender_mcp_adapter_only_bridges_to_tender_application() -> None:
    adapter_imports = _imported_modules(APP_ROOT / "interfaces" / "agent" / "tender_mcp.py")

    assert "mcp.server.fastmcp" in adapter_imports
    assert "app.modules.agent.tender.application.service" in adapter_imports
    assert not any(module.startswith("app.infrastructure") for module in adapter_imports)
    assert not any(module.startswith("app.modules.knowledge") for module in adapter_imports)


def test_targeted_architecture_packages_exist_and_old_packages_are_gone() -> None:
    expected_paths = (
        APP_ROOT / "modules" / "ingestion" / "domain",
        APP_ROOT / "modules" / "ingestion" / "ports",
        APP_ROOT / "modules" / "knowledge" / "domain",
        APP_ROOT / "modules" / "knowledge" / "ports",
        APP_ROOT / "modules" / "online" / "domain" / "checklist",
        APP_ROOT / "interfaces" / "agent" / "contracts.py",
        APP_ROOT / "infrastructure" / "filesystem",
        APP_ROOT / "infrastructure" / "ocr",
        APP_ROOT / "composition" / "online.py",
        APP_ROOT / "composition" / "agent.py",
        APP_ROOT / "composition" / "knowledge.py",
        APP_ROOT / "composition" / "ingestion.py",
        APP_ROOT / "composition" / "runtime.py",
    )
    assert all(path.exists() for path in expected_paths)

    old_paths = (
        APP_ROOT / "api",
        APP_ROOT / "application",
        APP_ROOT / "bridges",
        APP_ROOT / "core",
        APP_ROOT / "db",
        APP_ROOT / "domain",
        APP_ROOT / "models",
        APP_ROOT / "repositories",
        APP_ROOT / "schemas",
        APP_ROOT / "services",
    )
    assert all(not path.exists() for path in old_paths)


def test_online_decision_is_composed_from_knowledge_query_capability() -> None:
    root_source = (APP_ROOT / "composition" / "root.py").read_text(encoding="utf-8")
    assert (
        "build_rule_retrieval_service(\n                self.knowledge_query_capability()"
        in root_source
    )
    assert (
        "build_decision_service(\n                self.knowledge_query_capability()"
        in root_source
    )


def test_sensitive_ocr_outputs_are_not_kept_in_tests() -> None:
    assert not (PROJECT_ROOT / "tests" / "ocr").exists()
    assert not (PROJECT_ROOT / "tests" / "ocr" / "output").exists()

    classifier_source = (PROJECT_ROOT / "tools" / "ocr" / "classify_sample_inventory.py").read_text(
        encoding="utf-8"
    )
    ocr_source = (PROJECT_ROOT / "tools" / "ocr" / "tencent_ocr_mvp.py").read_text(
        encoding="utf-8"
    )
    assert "tests/ocr/output" not in classifier_source
    assert "tests/ocr/output" not in ocr_source
