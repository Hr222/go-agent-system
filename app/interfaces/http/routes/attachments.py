from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.interfaces.http.dependencies import get_attachment_storage
from app.interfaces.http.schemas.attachment import AttachmentUploadResponse
from app.modules.attachment import AttachmentStoragePort

router = APIRouter()


@router.post(
    "/upload",
    response_model=AttachmentUploadResponse,
    responses={400: {"description": "附件上传输入无效。"}},
)
@router.post(
    "",
    response_model=AttachmentUploadResponse,
    include_in_schema=False,
)
async def upload_attachment(
    file: UploadFile = File(...),
    storage: AttachmentStoragePort = Depends(get_attachment_storage),
) -> AttachmentUploadResponse:
    """Stage a generic attachment without invoking any business capability."""

    try:
        attachment = storage.stage_attachment(
            file_name=file.filename,
            media_type=file.content_type,
            file_stream=file.file,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_INPUT", "message": "附件上传内容无效。"},
        ) from exc
    finally:
        await file.close()

    return AttachmentUploadResponse(**attachment.public_dict())

