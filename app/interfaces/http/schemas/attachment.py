from __future__ import annotations

from pydantic import BaseModel, Field


class AttachmentUploadResponse(BaseModel):
    """Client-safe metadata returned after an attachment is staged."""

    attachment_id: str = Field(description="服务端生成的不透明附件 ID。")
    file_name: str = Field(description="规范化后的原始文件名。")
    media_type: str = Field(description="附件媒体类型。")
    size_bytes: int = Field(ge=1, description="附件字节数。")
    sha256: str = Field(description="附件内容 SHA-256 摘要。")
    status: str = Field(default="available", description="附件生命周期状态。")

