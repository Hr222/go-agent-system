"""兼容旧引用的数据获取协议导出。

当前 D3 已将数据获取能力迁入 `policy_data_acquisition`，
这里保留旧导出，避免现有引用路径立刻失效。
"""

from app.business.online.application.data_acquisition.contracts import (
    ChecklistDataAcquisitionRequest,
    ChecklistDataProvider,
)
from app.business.online.application.data_acquisition.models import (
    ChecklistDataFieldTrace,
    ChecklistDataPack,
)

__all__ = [
    "ChecklistDataAcquisitionRequest",
    "ChecklistDataFieldTrace",
    "ChecklistDataPack",
    "ChecklistDataProvider",
]
