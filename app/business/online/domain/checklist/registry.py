from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.business.online.domain.checklist.definitions import ChecklistScenarioDefinition


class ScenarioNotFoundError(ValueError):
    """当调用方请求不存在的场景时，返回统一错误。"""


@dataclass(slots=True)
class ChecklistScenarioRegistry:
    """统一维护当前系统已注册的 checklist 场景定义。"""

    _definitions: dict[str, ChecklistScenarioDefinition]
    _default_scenario_code: str | None = field(init=False, default=None, repr=False)

    def __init__(
        self,
        definitions: Iterable[ChecklistScenarioDefinition] = (),
        *,
        default_scenario_code: str | None = None,
    ) -> None:
        self._definitions = {}
        self._default_scenario_code = default_scenario_code
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ChecklistScenarioDefinition) -> None:
        """注册单个场景定义，注册表本身不感知具体业务场景。"""
        normalized_code = definition.scenario_code.strip()
        if not normalized_code:
            raise ValueError("scenario_code 不能为空。")
        if normalized_code in self._definitions:
            raise ValueError(f"场景已注册：{normalized_code}")
        self._definitions[normalized_code] = definition
        if self._default_scenario_code is None:
            self._default_scenario_code = normalized_code

    def get(self, scenario_code: str) -> ChecklistScenarioDefinition:
        """按场景编码获取定义，不存在时抛出统一异常。"""
        definition = self._definitions.get(scenario_code)
        if definition is None:
            raise ScenarioNotFoundError(f"未注册的 checklist 场景：{scenario_code}")
        return definition

    def default(self) -> ChecklistScenarioDefinition:
        """返回未指定场景时使用的默认场景定义。"""
        if self._default_scenario_code is None:
            raise ScenarioNotFoundError("当前未注册有效的 checklist 场景。")
        return self.get(self._default_scenario_code)

    def list_all(self) -> tuple[ChecklistScenarioDefinition, ...]:
        """列出当前已接入的全部 checklist 场景。"""
        return tuple(self._definitions.values())
