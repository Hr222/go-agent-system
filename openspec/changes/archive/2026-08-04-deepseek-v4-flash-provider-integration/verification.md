# Verification

## Local verification

- Targeted Provider, structured normalization, composition, application-container, and existing GLM tests passed: `36 passed`.
- `python -m pytest -q tests/infrastructure/test_openai_client_factory.py tests/infrastructure/test_langchain_chat_adapter.py tests/agent/tender/test_llm_adapter.py tests/agent/tender/test_structured_output_normalization.py tests/application/test_application_container.py tests/infrastructure/test_deepseek_provider.py` is the target command for the final local run.
- `ruff check app tests` passed.
- `python -m compileall -q app tests tools` passed.
- `openspec.cmd validate deepseek-v4-flash-provider-integration --strict` passed.
- Full suite result: `191 passed, 3 failed`; the three failures are existing PostgreSQL integration tests timing out against unavailable `127.0.0.1:5432`, outside this change.

## DeepSeek MVP verification

- Provider: `deepseek`
- Model: `deepseek-v4-flash`
- Network and ordinary Chat diagnostic: passed; DNS/TCP/HTTPS succeeded, Chat returned `content_chars=3`, `reasoning_chars=0`.
- Single-chunk Tender Structured smoke: passed; JSON Object request, disabled thinking, local `TenderChunkAnalysis` validation, input `154` chars, output `521` chars, duration `2432.71` ms.
- The initial no-key precheck correctly returned `not_configured`; no secret value was recorded.
- No API key, complete prompt, complete response, or tender source text is recorded here.
- This change does not claim Tender global merge, multi-volume acceptance, or DOCX business delivery.
