# llm-chat-streaming

将 LLM 单轮对话改为支持流式输出。

## 验证记录

- `python -m pytest tests/application/test_llm_stream_http.py tests/llm/test_chat_application.py tests/infrastructure/test_langchain_chat_adapter.py tests/application/test_llm_http.py -q` 通过（22 项）。
- `python -m pytest tests/architecture/test_architecture_boundaries.py tests/application/test_llm_stream_http.py -q` 通过（19 项）。
- `ruff check app tests` 和 `python -m compileall -q app tests` 通过。
- `cd frontend; npm.cmd test` 通过（5 项）；`npm.cmd run build` 通过。

## 流式验收

- 使用 `tests/application/streaming_acceptance_app.py` 作为假 Provider 后端，以 `tests/support/streaming_proxy.py` 代理其 TCP 流。`curl.exe --no-buffer --max-time 0.25 ...` 在 `256ms` 内收到 `meta` 和首个 `delta` （`first`），二个片段仍在上游延迟，证明代理未缓冲首个事件。
- 该 `curl` 截止模拟客户端中止；前端 `AbortSignal` 测试验证浏览器取消会传播到 `fetch`。
- 流式 HTTP 验收测试覆盖慢首 Token 返回 `504`、部分输出后错误，以及并发容量耗尽时的 `429` 且不调用 Provider。
- `docker/nginx/llm-streaming.conf` 包含 HTTP/1.1、禁用缓冲、超时和连接配置；Docker 守护进程可用，但 Docker Hub 不可连接，因此上述验收代理未使用外部 Nginx 镜像。
