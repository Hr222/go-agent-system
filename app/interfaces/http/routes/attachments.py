from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.interfaces.http.dependencies import get_attachment_storage
from app.interfaces.http.schemas.attachment import AttachmentUploadResponse
from app.interfaces.http.security import get_request_principal
from app.platform.attachment import AttachmentAccessContext, AttachmentStoragePort
from app.platform.security import RequestPrincipal

router = APIRouter()


@router.get(
    "/{attachment_id}/download",
    responses={404: {"description": "资源不可用。"}},
)
def download_attachment(
    attachment_id: str,
    conversation_id: UUID,
    storage: AttachmentStoragePort = Depends(get_attachment_storage),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> Response:
    """Return a staged attachment only when its trusted access context matches."""

    try:
        read_result = storage.read(
            attachment_id,
            context=AttachmentAccessContext(
                subject=principal.subject,
                conversation_id=str(conversation_id),
            ),
        )
    except Exception:  # noqa: BLE001 - do not leak storage state through this endpoint
        read_result = None
    if (
        read_result is None
        or read_result.status != "available"
        or read_result.attachment is None
        or read_result.content is None
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "ATTACHMENT_UNAVAILABLE", "message": "资源不可用。"},
        )

    file_name = quote(read_result.attachment.file_name, safe="")
    return Response(
        content=read_result.content,
        media_type=read_result.attachment.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{file_name}",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/upload",
    response_model=AttachmentUploadResponse,
    responses={
        400: {"description": "附件上传输入无效。"},
        403: {"description": "附件上传需要可信主体。"},
    },
)
@router.post(
    "",
    response_model=AttachmentUploadResponse,
    include_in_schema=False,
)
async def upload_attachment(
    file: UploadFile = File(...),
    conversation_id: UUID | None = Form(default=None),
    storage: AttachmentStoragePort = Depends(get_attachment_storage),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> AttachmentUploadResponse:
    """Stage a generic attachment without invoking any business capability."""

    if not isinstance(principal.subject, str) or not principal.subject.strip():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ATTACHMENT_PRINCIPAL_REQUIRED",
                "message": "上传附件需要可信请求主体。",
            },
        )

    try:
        attachment = storage.stage_attachment(
            file_name=file.filename,
            media_type=file.content_type,
            file_stream=file.file,
            context=AttachmentAccessContext(
                subject=principal.subject,
                conversation_id=str(conversation_id) if conversation_id is not None else None,
            ),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_INPUT", "message": "附件上传内容无效。"},
        ) from exc
    finally:
        await file.close()

    return AttachmentUploadResponse(**attachment.public_dict())
