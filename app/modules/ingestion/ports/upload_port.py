from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(slots=True, frozen=True)
class StagedUpload:
    """上传暂存后供入库用例消费的文件信息。"""

    upload_id: str
    file_name: str
    stored_path: str
    size_bytes: int


class UploadStoragePort(Protocol):
    """HTTP 上传流程依赖的暂存文件能力。"""

    def stage_upload(self, *, file_name: str | None, file_stream: BinaryIO) -> StagedUpload: ...

    def resolve_upload(self, upload_id: str) -> str: ...

    def promote_upload(self, upload_id: str) -> str: ...

    def discard_upload(self, upload_id: str) -> None: ...
