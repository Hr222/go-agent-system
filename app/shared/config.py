from dataclasses import dataclass
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProviderName = Literal["glm", "deepseek"]
GlmRuntimeProfileName = Literal["resource", "coding_plan"]
GlmThinkingMode = Literal["disabled", "enabled", "low", "high", "max"]
PrincipalMode = Literal["anonymous", "static"]

_GLM_RESOURCE_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
_GLM_RESOURCE_DEFAULT_MODEL = "glm-4.5-air"
_GLM_CODING_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"
_GLM_CODING_DEFAULT_MODEL = "glm-5.3"
_GLM_DEFAULT_TIMEOUT_SECONDS = 60.0
_GLM_DEFAULT_TEMPERATURE = 0.0
_GLM_DEFAULT_MAX_TOKENS = 16_384
_GLM_RESOURCE_DEFAULT_THINKING: GlmThinkingMode = "disabled"
_GLM_CODING_DEFAULT_THINKING: GlmThinkingMode = "low"


@dataclass(frozen=True, slots=True)
class LlmProviderConfig:
    """一个 OpenAI-compatible LLM Provider 的运行时配置。"""

    provider: LlmProviderName
    api_key: str | None
    base_url: str
    model: str | None
    timeout_seconds: float
    temperature: float
    max_tokens: int | None
    thinking: GlmThinkingMode | None = None
    runtime_profile: GlmRuntimeProfileName | None = None


@dataclass(frozen=True, slots=True)
class LlmRetryConfig:
    """OpenAI-compatible 调用的应用级瞬态失败重试配置。"""

    max_attempts: int
    base_backoff_seconds: float
    max_backoff_seconds: float
    max_retry_after_seconds: float
    total_backoff_budget_seconds: float


class Settings(BaseSettings):
    """应用配置：优先从环境变量和 `.env` 中加载。"""

    app_name: str = "Go Agent System"
    app_version: str = "0.1.0"
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(default=9205, gt=0, le=65535)
    api_v1_prefix: str = "/api/v1"
    request_principal_mode: PrincipalMode = Field(
        default="anonymous",
        alias="REQUEST_PRINCIPAL_MODE",
    )
    static_principal_subject: str = Field(
        default="",
        alias="STATIC_PRINCIPAL_SUBJECT",
    )
    static_principal_permissions: str = Field(
        default="",
        alias="STATIC_PRINCIPAL_PERMISSIONS",
    )
    policy_pipeline_workspace: str = ".runtime/policy_pipeline"
    policy_upload_max_size_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    policy_upload_retention_seconds: int = Field(default=24 * 60 * 60, gt=0)
    attachment_storage_workspace: str = ".runtime/attachments"
    attachment_max_size_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    attachment_retention_seconds: int = Field(default=24 * 60 * 60, gt=0)
    attachment_allowed_media_types: str = (
        "application/msword,"
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "image/bmp,image/jpeg,image/png,image/tiff,image/webp"
    )
    tender_upload_max_size_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    tender_hard_max_size_bytes: int = Field(
        default=70 * 1024 * 1024, gt=0, alias="TENDER_HARD_MAX_SIZE_BYTES"
    )
    tender_max_uncompressed_bytes: int = Field(
        default=250 * 1024 * 1024, gt=0, alias="TENDER_MAX_UNCOMPRESSED_BYTES"
    )
    tender_max_zip_entries: int = Field(
        default=10_000, gt=0, alias="TENDER_MAX_ZIP_ENTRIES"
    )
    tender_max_compression_ratio: float = Field(
        default=200.0, gt=0, alias="TENDER_MAX_COMPRESSION_RATIO"
    )
    tender_chunk_threshold_bytes: int = Field(
        default=4 * 1024 * 1024, gt=0, alias="TENDER_CHUNK_THRESHOLD_BYTES"
    )
    tender_chunk_input_chars: int = Field(
        default=8_000, gt=128, alias="TENDER_CHUNK_INPUT_CHARS"
    )
    tender_merge_input_chars: int = Field(
        default=18_000, gt=128, alias="TENDER_MERGE_INPUT_CHARS"
    )
    tender_max_output_chars: int = Field(
        default=16_000, gt=0, alias="TENDER_MAX_OUTPUT_CHARS"
    )
    tender_max_chunks: int = Field(default=128, gt=0, alias="TENDER_MAX_CHUNKS")
    tender_max_merge_items: int = Field(default=8, gt=0, alias="TENDER_MAX_MERGE_ITEMS")
    tender_max_llm_calls: int = Field(default=160, gt=0, alias="TENDER_MAX_LLM_CALLS")
    tender_max_retries: int = Field(default=1, ge=0, le=3, alias="TENDER_MAX_RETRIES")
    tender_max_total_seconds: float = Field(
        default=300.0, gt=0, alias="TENDER_MAX_TOTAL_SECONDS"
    )

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
    llm_provider: LlmProviderName = Field(default="glm", alias="LLM_PROVIDER")
    zhipu_api_key: str | None = Field(default=None, alias="ZHIPU_API_KEY")
    glm_runtime_profile: GlmRuntimeProfileName = Field(
        default="resource",
        alias="GLM_RUNTIME_PROFILE",
    )
    zhipu_resource_base_url: str | None = Field(
        default=None,
        alias="ZHIPU_RESOURCE_BASE_URL",
    )
    zhipu_resource_chat_model: str | None = Field(
        default=None,
        alias="ZHIPU_RESOURCE_CHAT_MODEL",
    )
    zhipu_resource_timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        alias="ZHIPU_RESOURCE_TIMEOUT_SECONDS",
    )
    zhipu_resource_temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
        alias="ZHIPU_RESOURCE_TEMPERATURE",
    )
    zhipu_resource_max_tokens: int | None = Field(
        default=None,
        gt=0,
        alias="ZHIPU_RESOURCE_MAX_TOKENS",
    )
    zhipu_resource_thinking: GlmThinkingMode = Field(
        default=_GLM_RESOURCE_DEFAULT_THINKING,
        alias="ZHIPU_RESOURCE_THINKING",
    )
    zhipu_coding_base_url: str | None = Field(
        default=None,
        alias="ZHIPU_CODING_BASE_URL",
    )
    zhipu_coding_chat_model: str | None = Field(
        default=None,
        alias="ZHIPU_CODING_CHAT_MODEL",
    )
    zhipu_coding_timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        alias="ZHIPU_CODING_TIMEOUT_SECONDS",
    )
    zhipu_coding_temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
        alias="ZHIPU_CODING_TEMPERATURE",
    )
    zhipu_coding_max_tokens: int | None = Field(
        default=None,
        gt=0,
        alias="ZHIPU_CODING_MAX_TOKENS",
    )
    zhipu_coding_thinking: GlmThinkingMode = Field(
        default=_GLM_CODING_DEFAULT_THINKING,
        alias="ZHIPU_CODING_THINKING",
    )
    # 旧变量仅作为 resource Profile 的迁移回退，避免已有部署升级后失效。
    zhipu_base_url: str | None = Field(default=None, alias="ZHIPU_BASE_URL")
    zhipu_chat_model: str | None = Field(default=None, alias="ZHIPU_CHAT_MODEL")
    zhipu_timeout_seconds: float | None = Field(
        default=_GLM_DEFAULT_TIMEOUT_SECONDS,
        gt=0,
        alias="ZHIPU_TIMEOUT_SECONDS",
    )
    zhipu_temperature: float | None = Field(
        default=_GLM_DEFAULT_TEMPERATURE,
        ge=0,
        le=2,
        alias="ZHIPU_TEMPERATURE",
    )
    zhipu_max_tokens: int | None = Field(
        default=_GLM_DEFAULT_MAX_TOKENS,
        gt=0,
        alias="ZHIPU_MAX_TOKENS",
    )
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_chat_model: str | None = Field(
        default="deepseek-v4-flash", alias="DEEPSEEK_CHAT_MODEL"
    )
    deepseek_timeout_seconds: float = Field(
        default=60.0, gt=0, alias="DEEPSEEK_TIMEOUT_SECONDS"
    )
    deepseek_temperature: float = Field(
        default=0.0, ge=0, le=2, alias="DEEPSEEK_TEMPERATURE"
    )
    deepseek_max_tokens: int | None = Field(
        default=16_384, gt=0, alias="DEEPSEEK_MAX_TOKENS"
    )
    deepseek_thinking: Literal["enabled", "disabled"] = Field(
        default="disabled", alias="DEEPSEEK_THINKING"
    )
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
    llm_retry_max_attempts: int = Field(
        default=2,
        ge=1,
        le=3,
        alias="LLM_RETRY_MAX_ATTEMPTS",
    )
    llm_retry_base_backoff_seconds: float = Field(
        default=1.0,
        gt=0,
        alias="LLM_RETRY_BASE_BACKOFF_SECONDS",
    )
    llm_retry_max_backoff_seconds: float = Field(
        default=8.0,
        gt=0,
        alias="LLM_RETRY_MAX_BACKOFF_SECONDS",
    )
    llm_retry_max_retry_after_seconds: float = Field(
        default=30.0,
        gt=0,
        alias="LLM_RETRY_MAX_RETRY_AFTER_SECONDS",
    )
    llm_retry_total_backoff_budget_seconds: float = Field(
        default=30.0,
        gt=0,
        alias="LLM_RETRY_TOTAL_BACKOFF_BUDGET_SECONDS",
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
    interaction_proposal_ttl_seconds: float = Field(
        default=300.0,
        gt=0,
        alias="INTERACTION_PROPOSAL_TTL_SECONDS",
    )
    ocr_enabled: bool = True
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator(
        "zhipu_resource_max_tokens",
        "zhipu_coding_max_tokens",
        "zhipu_max_tokens",
        "deepseek_max_tokens",
        mode="before",
    )
    @classmethod
    def _empty_max_tokens_as_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _validate_principal_configuration(self) -> "Settings":
        if self.request_principal_mode == "static" and not self.static_principal_subject.strip():
            raise ValueError(
                "STATIC_PRINCIPAL_SUBJECT is required when REQUEST_PRINCIPAL_MODE=static"
            )
        if self.llm_retry_base_backoff_seconds > self.llm_retry_max_backoff_seconds:
            raise ValueError(
                "LLM_RETRY_BASE_BACKOFF_SECONDS cannot exceed "
                "LLM_RETRY_MAX_BACKOFF_SECONDS"
            )
        return self

    @property
    def static_principal_permission_tuple(self) -> tuple[str, ...]:
        """Return normalized server-configured static principal permissions."""

        return tuple(
            sorted(
                {
                    permission.strip()
                    for permission in self.static_principal_permissions.split(",")
                    if permission.strip()
                }
            )
        )

    @property
    def attachment_allowed_media_type_tuple(self) -> tuple[str, ...]:
        """Return normalized server-configured attachment media types."""

        return tuple(
            sorted(
                {
                    media_type.strip().lower()
                    for media_type in self.attachment_allowed_media_types.split(",")
                    if media_type.strip()
                }
            )
        )

    @property
    def llm_retry_config(self) -> LlmRetryConfig:
        """返回当前进程共享的 LLM 应用级重试参数。"""

        return LlmRetryConfig(
            max_attempts=self.llm_retry_max_attempts,
            base_backoff_seconds=self.llm_retry_base_backoff_seconds,
            max_backoff_seconds=self.llm_retry_max_backoff_seconds,
            max_retry_after_seconds=self.llm_retry_max_retry_after_seconds,
            total_backoff_budget_seconds=self.llm_retry_total_backoff_budget_seconds,
        )

    @property
    def llm_stream_first_activity_timeout_seconds(self) -> float:
        """为流式首 activity 等待预留受限的内部重试时间。"""

        return (
            self.llm_stream_first_token_timeout_seconds * self.llm_retry_max_attempts
            + (
                self.llm_retry_total_backoff_budget_seconds
                if self.llm_retry_max_attempts > 1
                else 0.0
            )
        )

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

    def llm_provider_config(self, provider: LlmProviderName | None = None) -> LlmProviderConfig:
        selected = provider or self.llm_provider
        if selected == "glm":
            return self._glm_provider_config()
        if selected == "deepseek":
            return LlmProviderConfig(
                provider="deepseek",
                api_key=self.deepseek_api_key,
                base_url=self.deepseek_base_url,
                model=self.deepseek_chat_model,
                timeout_seconds=self.deepseek_timeout_seconds,
                temperature=self.deepseek_temperature,
                max_tokens=self.deepseek_max_tokens,
                thinking=self.deepseek_thinking,
            )
        raise ValueError(f"未注册的 LLM Provider：{selected}")

    def _glm_provider_config(self) -> LlmProviderConfig:
        if self.glm_runtime_profile == "coding_plan":
            return LlmProviderConfig(
                provider="glm",
                api_key=self.zhipu_api_key,
                base_url=_configured_or_default(
                    self.zhipu_coding_base_url,
                    _GLM_CODING_DEFAULT_BASE_URL,
                ),
                model=_configured_or_default(
                    self.zhipu_coding_chat_model,
                    _GLM_CODING_DEFAULT_MODEL,
                ),
                timeout_seconds=_configured_or_default(
                    self.zhipu_coding_timeout_seconds,
                    _GLM_DEFAULT_TIMEOUT_SECONDS,
                ),
                temperature=_configured_or_default(
                    self.zhipu_coding_temperature,
                    _GLM_DEFAULT_TEMPERATURE,
                ),
                max_tokens=_configured_or_default(
                    self.zhipu_coding_max_tokens,
                    _GLM_DEFAULT_MAX_TOKENS,
                ),
                thinking=self.zhipu_coding_thinking,
                runtime_profile="coding_plan",
            )

        return LlmProviderConfig(
            provider="glm",
            api_key=self.zhipu_api_key,
            base_url=_configured_or_default(
                self.zhipu_resource_base_url,
                self.zhipu_base_url,
                _GLM_RESOURCE_DEFAULT_BASE_URL,
            ),
            model=_configured_or_default(
                self.zhipu_resource_chat_model,
                self.zhipu_chat_model,
                _GLM_RESOURCE_DEFAULT_MODEL,
            ),
            timeout_seconds=_configured_or_default(
                self.zhipu_resource_timeout_seconds,
                self.zhipu_timeout_seconds,
                _GLM_DEFAULT_TIMEOUT_SECONDS,
            ),
            temperature=_configured_or_default(
                self.zhipu_resource_temperature,
                self.zhipu_temperature,
                _GLM_DEFAULT_TEMPERATURE,
            ),
            max_tokens=_configured_or_default(
                self.zhipu_resource_max_tokens,
                self.zhipu_max_tokens,
                _GLM_DEFAULT_MAX_TOKENS,
            ),
            thinking=self.zhipu_resource_thinking,
            runtime_profile="resource",
        )


def _configured_or_default(value: object, *fallbacks: object) -> object:
    """返回首个非空配置值，保留 `0` 等经字段校验后合法的值。"""

    for candidate in (value, *fallbacks):
        if candidate is not None:
            return candidate
    raise RuntimeError("缺少 GLM Profile 默认配置。")


settings = Settings()
