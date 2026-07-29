from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request

from app.composition.runtime import inspect_knowledge_base_schema
from app.interfaces.http.dependencies import get_stateless_application_container
from app.interfaces.http.router import api_router
from app.shared.config import settings
from app.shared.logging import configure_logging, get_logger

configure_logging(settings.log_level)
logger = get_logger("app.main")


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # 应用启动时只做轻量表结构检查，不主动创建或修改数据库结构。
        logger.info(
            "启动 FastAPI 应用 name=%s version=%s log_level=%s",
            settings.app_name,
            settings.app_version,
            settings.log_level.upper(),
        )
        schema_status = inspect_knowledge_base_schema()
        missing_tables = schema_status.missing_tables
        if missing_tables is None:
            logger.warning("数据库不可用，已跳过知识库表结构检查。")
        elif missing_tables:
            logger.warning(
                "知识库表结构未就绪 missing_tables=%s。%s",
                ",".join(missing_tables),
                schema_status.setup_guide,
            )
        else:
            logger.info("知识库表结构检查通过。")
        application.state.llm_stream_slots = asyncio.Semaphore(
            settings.llm_stream_max_concurrency
        )
        application.state.llm_active_streams = 0
        yield
        get_stateless_application_container().close()
        get_stateless_application_container.cache_clear()
        logger.info("关闭 FastAPI 应用 name=%s", settings.app_name)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    application.state.llm_stream_slots = asyncio.Semaphore(settings.llm_stream_max_concurrency)
    application.state.llm_active_streams = 0

    @application.middleware("http")
    async def log_requests(request: Request, call_next):
        # 统一记录请求耗时和状态，便于定位接口层、应用层或基础设施层的失败。
        started = perf_counter()
        client_host = request.client.host if request.client else "-"
        path = request.url.path
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started) * 1000
            logger.exception(
                "未处理的请求异常 method=%s path=%s client=%s duration_ms=%.2f",
                request.method,
                path,
                client_host,
                duration_ms,
            )
            raise

        matched_route = request.scope.get("route")
        route_template = getattr(matched_route, "path", path)
        duration_ms = (perf_counter() - started) * 1000
        status_code = response.status_code
        if status_code >= 500:
            log_method = logger.error
        elif status_code >= 400:
            log_method = logger.warning
        else:
            log_method = logger.info

        log_method(
            "HTTP request method=%s path=%s route=%s status=%s client=%s duration_ms=%.2f",
            request.method,
            path,
            route_template,
            status_code,
            client_host,
            duration_ms,
        )
        return response

    @application.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "message": "Go Agent System API",
            "phase": "phase-3-f1",
            "frontend": "http://127.0.0.1:5426",
        }

    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
