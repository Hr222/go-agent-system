from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.platform.ingestion.contracts import IntakeValidationResult, RegisteredFileInfo
from app.platform.ingestion.domain import PolicyIntakePolicy


class PolicyFileService:
    """处理源文件登记，并把准入规则委托给领域层。"""

    def __init__(self, intake_policy: PolicyIntakePolicy | None = None) -> None:
        self.intake_policy = intake_policy or PolicyIntakePolicy()

    def register_file(self, source_path: str) -> RegisteredFileInfo:
        """
        读取源文件的不可变元数据。

        对应流水线步骤 1，本方法不应修改任何源文件内容。
        """
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"源文件不存在：{source_path}")
        if not path.is_file():
            raise IsADirectoryError(f"源路径不是文件：{source_path}")

        stat = path.stat()
        return RegisteredFileInfo(
            source_path=str(path),
            file_name=path.name,
            extension=path.suffix.lower(),
            size_bytes=stat.st_size,
            sha256=self._hash_file(path),
            source_modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    def validate_intake(self, registered_file: RegisteredFileInfo) -> IntakeValidationResult:
        """
        步骤 2：在正式解析前执行轻量级准入校验。

        业务准入规则属于领域层，这里只负责把领域决策转换成 API DTO。
        """
        decision = self.intake_policy.decide(
            file_name=registered_file.file_name,
            extension=registered_file.extension,
            size_bytes=registered_file.size_bytes,
        )
        return IntakeValidationResult(
            is_allowed=decision.is_allowed,
            detected_file_kind=decision.detected_file_kind,
            needs_normalization=decision.needs_normalization,
            recommended_parse_method=decision.recommended_parse_method,
            warnings=decision.warnings,
        )

    def _hash_file(self, path: Path) -> str:
        """计算稳定的 SHA-256，用于去重和溯源。"""
        digest = sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
