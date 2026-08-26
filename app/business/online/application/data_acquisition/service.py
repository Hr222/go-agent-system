from __future__ import annotations

from app.business.online.application.data_acquisition.contracts import (
    ChecklistDataAcquisitionRequest,
)
from app.business.online.application.data_acquisition.models import ChecklistDataPack
from app.business.online.application.data_acquisition.providers import InlineChecklistDataProvider
from app.business.online.application.data_acquisition.registry import ChecklistDataProviderRegistry
from app.business.online.domain.checklist import ChecklistScenarioRegistry


class PolicyDataAcquisitionService:
    """面向业务场景消费数据提供者，并输出统一数据包。"""

    def __init__(
        self,
        provider_registry: ChecklistDataProviderRegistry | None = None,
        *,
        scenario_registry: ChecklistScenarioRegistry | None = None,
    ) -> None:
        if provider_registry is None:
            if scenario_registry is None:
                raise ValueError("未提供场景注册表，无法为数据 Provider 完成场景注册。")
            provider_registry = ChecklistDataProviderRegistry()
            default_provider = InlineChecklistDataProvider()
            for scenario in scenario_registry.list_all():
                provider_registry.register(scenario.scenario_code, default_provider)
        self.provider_registry = provider_registry

    def acquire_checklist_data(self, request: ChecklistDataAcquisitionRequest) -> ChecklistDataPack:
        """按场景收集本次核验所需的最小业务数据。"""
        provider = self.provider_registry.get(request.scenario_code)
        return provider.collect(request)
