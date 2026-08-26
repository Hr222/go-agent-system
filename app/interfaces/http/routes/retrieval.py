from fastapi import APIRouter, Depends, HTTPException

from app.business.online.application.ask_knowledge import AskKnowledgeUseCase
from app.interfaces.http.assemblers.rag import (
    ask_command,
    ask_response,
    search_command,
    search_response,
)
from app.interfaces.http.dependencies import get_ask_knowledge_use_case
from app.interfaces.http.schemas import (
    RagAskRequest,
    RagAskResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.shared.exceptions import (
    KnowledgeBaseSchemaUnavailableError,
    ServiceNotConfiguredError,
    UpstreamServiceError,
)

router = APIRouter()


@router.post("/retrieval/search", response_model=RetrievalSearchResponse)
async def search_knowledge_base(
    request: RetrievalSearchRequest,
    use_case: AskKnowledgeUseCase = Depends(get_ask_knowledge_use_case),
) -> RetrievalSearchResponse:
    """通过在线 RAG 外观层执行知识库检索。"""
    try:
        return search_response(use_case.search(search_command(request)))
    except KnowledgeBaseSchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/retrieval/ask", response_model=RagAskResponse)
async def ask_knowledge_base(
    request: RagAskRequest,
    use_case: AskKnowledgeUseCase = Depends(get_ask_knowledge_use_case),
) -> RagAskResponse:
    """通过在线 RAG 外观层执行先检索后问答的链路。"""
    try:
        return ask_response(use_case.execute(ask_command(request)))
    except KnowledgeBaseSchemaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ServiceNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
