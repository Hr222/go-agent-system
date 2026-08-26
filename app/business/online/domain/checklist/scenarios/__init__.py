"""具体业务场景定义。通用清单模型和注册表不依赖本包中的场景。"""

from app.business.online.domain.checklist.scenarios.court_evaluation_materials import (
    COURT_EVALUATION_MATERIALS_SCENARIO,
)

__all__ = ["COURT_EVALUATION_MATERIALS_SCENARIO"]
