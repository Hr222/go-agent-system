## 1. 基线与契约确认

- [x] 1.1 对照 `llm-chat` 规格、现有实现和 F1 进度文档，确认本 Change 只覆盖独立 LLM 单轮对话，不扩大到 Tender Agent
- [x] 1.2 核对 `POST /api/v1/llm/chat` 的请求、响应、状态码和“无上下文、无工具、无持久化”边界

## 2. 后端契约与错误分支

- [x] 2.1 为超长消息增加 HTTP `422` 契约测试，并验证不会进入 Application
- [x] 2.2 为空白消息增加 HTTP `400` 契约测试，并验证不会调用 LLM Port
- [x] 2.3 为 `ServiceNotConfiguredError` 增加 HTTP `503` 映射测试
- [x] 2.4 为 `UpstreamServiceError` 和空模型响应增加 HTTP `502` 映射测试
- [x] 2.5 运行 Application、HTTP、Infrastructure 和架构边界测试，确认 Application 不依赖具体 LLM SDK（定向验证：32 passed）

## 3. 前端行为验收

- [x] 3.1 检查 Chat 页面通过统一 Axios Client 和 React Query 调用 `/v1/llm/chat`
- [x] 3.2 完成人工验收：正常发送、加载态、回答信息、错误提示和失败重试
- [x] 3.3 确认页面文案只表达单轮模型调用，不宣称上下文、历史会话、流式输出、工具调用或 RAG 能力
- [x] 3.4 运行 `frontend` 的 TypeScript 检查和生产构建

## 4. 完成验证与归档准备

- [x] 4.1 运行 `openspec.cmd validate --all --strict` 并确认 Change artifacts 完整（strict 校验通过）
- [x] 4.2 运行 `python -m pytest -q`、`ruff check app tests` 和 `python -m compileall -q app tests`（数据库已重命名并完成全量验证）
- [x] 4.3 已记录验证结果和完成边界：只能宣布“LLM 单轮对话能力已完成并通过验收”，不能宣布 F1 或 Tender Agent 完成

## Verification evidence

- `openspec.cmd validate --all --strict --no-interactive --json`: 通过，1 个 Change 有效。
- `python -m pytest -q tests/application/test_llm_http.py tests/llm/test_chat_application.py tests/infrastructure/test_langchain_chat_adapter.py tests/infrastructure/test_openai_client_factory.py tests/architecture/test_architecture_boundaries.py tests/architecture/test_service_structure.py`: 32 passed，1 个既有 Starlette/httpx 弃用警告。
- `ruff check app tests`: 通过。
- `python -m compileall -q app tests`: 通过。
- `frontend`: `npm.cmd run build` 通过；Vite 仅报告已有的大 chunk 警告。
- `python -m pytest -q`: 数据库 `bid_document_agent` 已重命名为 `go_agent_system`，结果为 113 passed，1 个既有 Starlette/httpx 弃用警告。
- 排除既有 PostgreSQL/Gitee 外部依赖测试后运行全套回归：109 passed，1 个既有 Starlette/httpx 弃用警告。
