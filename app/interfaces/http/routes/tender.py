from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.composition import ApplicationContainer
from app.interfaces.http.dependencies import get_stateless_application_container
from app.interfaces.http.schemas.tender import (
    TenderArtifactResponse,
    TenderErrorResponse,
    TenderGenerateSkeletonResponse,
)
from app.modules.agent.tender.contracts import TenderGenerateSkeletonCommand
from app.modules.agent.tender.errors import (
    TenderAnalysisError,
    TenderDocumentParseError,
    TenderInputError,
    TenderRenderError,
)
from app.shared.config import settings
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError

router = APIRouter()


@router.post(
    "/skeleton",
    response_model=TenderGenerateSkeletonResponse,
    responses={
        400: {"model": TenderErrorResponse},
        422: {"model": TenderErrorResponse},
        502: {"model": TenderErrorResponse},
        503: {"model": TenderErrorResponse},
    },
)
async def generate_tender_skeleton(
    file: UploadFile = File(...),
    user_focus: str | None = Form(default=None),
    container: ApplicationContainer = Depends(get_stateless_application_container),
) -> TenderGenerateSkeletonResponse:
    """同步执行 Tender Agent V1 骨架生成，不创建任务或保存原始文件。"""

    file_name = file.filename or ""
    try:
        content = await file.read()
    except Exception as exc:  # noqa: BLE001 - 协议层稳定转换
        raise _http_error("INVALID_INPUT", "招标文件读取失败。", 400) from exc
    finally:
        await file.close()

    if not content:
        raise _http_error("INVALID_INPUT", "招标文件不能为空。", 400)
    if len(content) > settings.tender_hard_max_size_bytes:
        raise _http_error("INVALID_INPUT", "招标文件超过服务端硬性大小限制。", 400)
    if len(content) > settings.tender_upload_max_size_bytes:
        raise _http_error("INVALID_INPUT", "招标文件超过大小限制。", 400)
    if not file_name.strip() or not file_name.lower().endswith(".docx"):
        raise _http_error("INVALID_INPUT", "Tender 只接收 DOCX 招标文件。", 400)

    try:
        application = container.tender_application()
        result = application.execute(
            TenderGenerateSkeletonCommand(
                file_name=file_name,
                content=content,
                user_focus=user_focus,
            )
        )
    except TenderInputError as exc:
        raise _http_error("INVALID_INPUT", str(exc), 400) from exc
    except TenderDocumentParseError as exc:
        raise _http_error("DOCUMENT_PARSE_FAILED", "招标 DOCX 解析失败。", 422) from exc
    except ServiceNotConfiguredError as exc:
        raise _http_error("SERVICE_NOT_CONFIGURED", "Tender Agent 模型服务尚未配置。", 503) from exc
    except UpstreamServiceError as exc:
        raise _http_error("UPSTREAM_FAILED", "Tender Agent 模型服务调用失败。", 502) from exc
    except TenderAnalysisError as exc:
        raise _http_error("ANALYSIS_FAILED", "招标文件结构化分析结果无效。", 422) from exc
    except TenderRenderError as exc:
        raise _http_error("RENDER_FAILED", "投标骨架文件生成失败。", 500) from exc

    return TenderGenerateSkeletonResponse(
        analysis=result.analysis,
        artifacts=[
            TenderArtifactResponse(
                file_name=artifact.file_name,
                media_type=artifact.media_type,
                size_bytes=len(artifact.content),
                content_base64=base64.b64encode(artifact.content).decode("ascii"),
            )
            for artifact in result.artifacts
        ],
        model=result.model,
        prompt_version=result.prompt_version,
    )


def _http_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
