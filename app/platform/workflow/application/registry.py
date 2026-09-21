from __future__ import annotations

from collections.abc import Iterable

from app.platform.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.platform.workflow.domain import WorkflowValidationError, WorkflowVersion
from app.platform.workflow.ports.registry import WorkflowDefinitionRegistryPort


class WorkflowDefinitionRegistry(WorkflowDefinitionRegistryPort):
    """Composition 创建的一次性不可变 Version 注册表。"""

    def __init__(
        self,
        versions: Iterable[WorkflowVersion],
        capability_catalog: CapabilityCatalogPort,
        *,
        validation_permissions: Iterable[str] = (),
    ) -> None:
        self._versions: dict[str, WorkflowVersion] = {}
        self._catalog = capability_catalog
        self._validation_permissions = tuple(validation_permissions)
        for version in versions:
            if version.key in self._versions:
                raise WorkflowValidationError("Workflow Version 标识不能重复。")
            self._validate_version(version)
            self._versions[version.key] = version

    def get(self, workflow_code: str, version: str) -> WorkflowVersion | None:
        return self._versions.get(f"{workflow_code}:{version}")

    def validate(self) -> None:
        for version in self._versions.values():
            self._validate_version(version)

    def validate_access(self, version: WorkflowVersion, permissions: Iterable[str]) -> None:
        if self._versions.get(version.key) is not version:
            raise WorkflowValidationError("Workflow Version 未注册。")
        for node in version.nodes:
            if self._catalog.get_available(node.capability_code, permissions=permissions) is None:
                raise PermissionError("当前主体无权使用 Workflow 能力。")

    def _validate_version(self, version: WorkflowVersion) -> None:
        for node in version.nodes:
            capability = self._catalog.get_available(
                node.capability_code,
                permissions=self._validation_permissions,
            )
            if capability is None or not capability.enabled:
                raise WorkflowValidationError(
                    f"Workflow 能力未注册或未启用：{node.capability_code}。"
                )
            if capability.code != node.capability_code:
                raise WorkflowValidationError("Workflow 能力绑定代码不一致。")
            properties = capability.input_schema.get("properties")
            if isinstance(properties, dict) and not set(node.input_fields).issubset(properties):
                raise WorkflowValidationError("Workflow 节点输入字段不符合能力契约。")
            if not set(capability.required_fields).issubset(node.input_fields):
                raise WorkflowValidationError("Workflow 节点未覆盖能力必需输入字段。")
            output_properties = capability.output_schema.get("properties")
            if isinstance(output_properties, dict) and not set(node.output_fields).issubset(
                output_properties
            ):
                raise WorkflowValidationError("Workflow 节点输出字段不符合能力契约。")
