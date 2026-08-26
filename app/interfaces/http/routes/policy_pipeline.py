from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.interfaces.http.assemblers.policy_pipeline import pipeline_command, pipeline_response
from app.interfaces.http.dependencies import (
    get_ingestion_preview_use_case,
    get_ingestion_use_case,
    get_policy_upload_service,
)
from app.interfaces.http.schemas import PolicyPipelineRequest, PolicyPipelineResponse
from app.interfaces.http.schemas.policy_upload import (
    PolicyUploadIngestRequest,
    PolicyUploadPreviewResponse,
)
from app.platform.ingestion.application.ingestion_use_case import IngestionUseCase
from app.platform.ingestion.ports import UploadStoragePort
from app.shared.exceptions import KnowledgeBaseSchemaUnavailableError
from app.shared.logging import get_logger

router = APIRouter()
logger = get_logger("app.interfaces.http.policy_pipeline")


@router.post("/policy-pipeline/preview", response_model=PolicyPipelineResponse)
async def preview_policy_pipeline(
    request: PolicyPipelineRequest,
    use_case: IngestionUseCase = Depends(get_ingestion_preview_use_case),
) -> PolicyPipelineResponse:
    """执行预览流水线，不写入数据库。"""
    try:
        return pipeline_response(use_case.preview(pipeline_command(request)))
    except (FileNotFoundError, IsADirectoryError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/policy-pipeline/ingest", response_model=PolicyPipelineResponse)
async def ingest_policy_pipeline(
    request: PolicyPipelineRequest,
    use_case: IngestionUseCase = Depends(get_ingestion_use_case),
) -> PolicyPipelineResponse:
    """执行完整流水线，并写入制度文档、版本、章节和切块。"""
    try:
        return pipeline_response(use_case.ingest(pipeline_command(request)))
    except KnowledgeBaseSchemaUnavailableError as exc:
        logger.exception("知识库表结构缺失，入库失败 path=%s", request.source_path)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/policy-pipeline/preview-upload", response_model=PolicyUploadPreviewResponse)
async def preview_policy_pipeline_upload(
    file: UploadFile = File(...),
    policy_category: str = Form("管理制度"),
    responsible_department: str | None = Form(None),
    version_label: str | None = Form(None),
    upload_service: UploadStoragePort = Depends(get_policy_upload_service),
    use_case: IngestionUseCase = Depends(get_ingestion_preview_use_case),
) -> PolicyUploadPreviewResponse:
    """接收 multipart 文件，暂存后交给入库预览用例。"""
    staged = None
    try:
        staged = upload_service.stage_upload(
            file_name=file.filename,
            file_stream=file.file,
        )
        response = use_case.preview(
            pipeline_command(
                PolicyPipelineRequest(
                    source_path=staged.stored_path,
                    policy_category=policy_category,
                    responsible_department=responsible_department,
                    version_label=version_label,
                    target_document_id=None,
                )
            )
        )
        return PolicyUploadPreviewResponse(
            **pipeline_response(response).model_dump(),
            upload_id=staged.upload_id,
        )
    except (FileNotFoundError, IsADirectoryError, RuntimeError, ValueError) as exc:
        if staged is not None:
            upload_service.discard_upload(staged.upload_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()


@router.post("/policy-pipeline/ingest-upload", response_model=PolicyPipelineResponse)
async def ingest_policy_pipeline_upload(
    request: PolicyUploadIngestRequest,
    upload_service: UploadStoragePort = Depends(get_policy_upload_service),
    use_case: IngestionUseCase = Depends(get_ingestion_use_case),
) -> PolicyPipelineResponse:
    """根据暂存 ID 找回文件，入库成功后删除对应暂存目录。"""
    try:
        source_path = upload_service.promote_upload(request.upload_id)
        response = pipeline_response(
            use_case.ingest(
                pipeline_command(
                    PolicyPipelineRequest(
                        source_path=source_path,
                        policy_category=request.policy_category,
                        responsible_department=request.responsible_department,
                        version_label=request.version_label,
                        target_document_id=request.target_document_id,
                    )
                )
            )
        )
        return response
    except KnowledgeBaseSchemaUnavailableError as exc:
        upload_service.discard_upload(request.upload_id)
        logger.exception("知识库表结构缺失，上传入库失败 upload_id=%s", request.upload_id)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError, RuntimeError, ValueError) as exc:
        upload_service.discard_upload(request.upload_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
