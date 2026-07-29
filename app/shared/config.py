from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：优先从环境变量和 `.env` 中加载。"""

    app_name: str = "Go Agent System"
    app_version: str = "0.1.0"
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(default=9205, gt=0, le=65535)
    api_v1_prefix: str = "/api/v1"
    policy_pipeline_workspace: str = ".runtime/policy_pipeline"
    policy_upload_max_size_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    policy_upload_retention_seconds: int = Field(default=24 * 60 * 60, gt=0)

    postgres_driver: str = "postgresql+psycopg"
    postgres_db: str = "go_agent_system"
    postgres_user: str = "admin"
    postgres_password: str = "123456"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_connect_timeout_seconds: int = Field(
        default=5,
        gt=0,
        le=60,
        alias="POSTGRES_CONNECT_TIMEOUT_SECONDS",
    )
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    gitee_api_key: str | None = Field(default=None, alias="GITEE_API_KEY")
    gitee_base_url: str = "https://ai.gitee.com/v1"
    embedding_model: str = "Qwen3-Embedding-0.6B"
    vector_dimensions: int = 1024
    chunk_target_chars: int = 1200
    chunk_overlap_chars: int = 120
    embedding_batch_size: int = 16
    zhipu_api_key: str | None = Field(default=None, alias="ZHIPU_API_KEY")
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_chat_model: str | None = "glm-4-flash"
    zhipu_timeout_seconds: float = Field(default=60.0, gt=0, alias="ZHIPU_TIMEOUT_SECONDS")
    zhipu_temperature: float = Field(default=0.0, ge=0, le=2, alias="ZHIPU_TEMPERATURE")
    zhipu_max_tokens: int | None = Field(default=None, gt=0, alias="ZHIPU_MAX_TOKENS")
    llm_stream_max_concurrency: int = Field(
        default=8, gt=0, alias="LLM_STREAM_MAX_CONCURRENCY"
    )
    llm_stream_first_token_timeout_seconds: float = Field(
        default=30.0, gt=0, alias="LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS"
    )
    llm_stream_idle_timeout_seconds: float = Field(
        default=20.0, gt=0, alias="LLM_STREAM_IDLE_TIMEOUT_SECONDS"
    )
    llm_stream_total_timeout_seconds: float = Field(
        default=120.0, gt=0, alias="LLM_STREAM_TOTAL_TIMEOUT_SECONDS"
    )
    llm_stream_heartbeat_seconds: float = Field(
        default=10.0, gt=0, alias="LLM_STREAM_HEARTBEAT_SECONDS"
    )
    ocr_max_pages_per_batch: int = 4
    ocr_image_max_side: int = 1800
    ocr_request_interval_seconds: float = 10.0
    tencent_ocr_secret_id: str | None = Field(default=None, alias="TENCENT_OCR_SECRET_ID")
    tencent_ocr_secret_key: str | None = Field(default=None, alias="TENCENT_OCR_SECRET_KEY")
    tencent_ocr_region: str = Field(default="ap-guangzhou", alias="TENCENT_OCR_REGION")
    tencent_ocr_endpoint: str = Field(
        default="ocr.tencentcloudapi.com",
        alias="TENCENT_OCR_ENDPOINT",
    )
    tencent_ocr_action: Literal["GeneralBasicOCR", "GeneralAccurateOCR"] = Field(
        default="GeneralAccurateOCR",
        alias="TENCENT_OCR_ACTION",
    )
    retrieval_top_k_default: int = 5
    retrieval_top_k_max: int = 20
    retrieval_min_score: float = 0.45
    retrieval_evidence_min_coverage: float = 0.15
    retrieval_evidence_rescue_margin: float = 0.04
    vector_search_strategy: Literal["exact", "hnsw"] = "exact"
    vector_search_hnsw_m: int = 16
    vector_search_hnsw_ef_construction: int = 64
    vector_search_hnsw_ef_search: int = 40
    rag_answer_top_k: int = 6
    rag_max_context_chars_per_chunk: int = 500
    ocr_enabled: bool = True
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    @property
    def database_url(self) -> str:
        """优先返回 `DATABASE_URL`，否则根据分项配置动态拼接连接串。"""
        if self.database_url_override:
            return self.database_url_override

        return (
            f"{self.postgres_driver}://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
