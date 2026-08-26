from __future__ import annotations

from typing import Protocol

from app.platform.ingestion.contracts import (
    IntakeValidationResult,
    RegisteredFileInfo,
)


class FileRegistrationPort(Protocol):
    """入库用例依赖的文件登记与准入能力。"""

    def register_file(self, source_path: str) -> RegisteredFileInfo: ...

    def validate_intake(self, registered_file: RegisteredFileInfo) -> IntakeValidationResult: ...
