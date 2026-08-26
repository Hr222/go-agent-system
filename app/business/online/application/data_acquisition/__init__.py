"""Checklist 决策输入材料获取能力。

本模块负责将请求体、表单或其他业务来源中的 Checklist 输入材料，
转换为统一的 ChecklistDataPack，供 Online Decision 使用。

本模块不负责知识库入库，也不负责 RAG 检索。
"""

from app.business.online.application.data_acquisition.contracts import (
    ChecklistDataAcquisitionRequest,
    ChecklistDataProvider,
    ChecklistInput,
)
from app.business.online.application.data_acquisition.models import (
    ChecklistDataFieldTrace,
    ChecklistDataPack,
)
from app.business.online.application.data_acquisition.providers import InlineChecklistDataProvider
from app.business.online.application.data_acquisition.registry import ChecklistDataProviderRegistry
from app.business.online.application.data_acquisition.service import PolicyDataAcquisitionService

__all__ = [
    "ChecklistDataAcquisitionRequest",
    "ChecklistInput",
    "ChecklistDataFieldTrace",
    "ChecklistDataPack",
    "ChecklistDataProvider",
    "ChecklistDataProviderRegistry",
    "InlineChecklistDataProvider",
    "PolicyDataAcquisitionService",
]
