## 1. 重试策略与配置

- [x] 1.1 在 `infrastructure/llm` 实现可注入时钟、睡眠和随机数的 Provider-neutral 瞬态失败分类与重试策略；覆盖 OpenAI/HTTPX 连接、超时、408、429、5xx 与不可重试 4xx。
- [x] 1.2 增加服务端重试配置及其校验：总尝试次数、基础/最大退避、最大 `Retry-After`、总退避预算和流式首 activity 的重试等待窗口；默认值保持 SDK 零重试与受限重试。
- [x] 1.3 为分类、`Retry-After`、抖动、次数耗尽、预算止损和安全日志增加替身测试，证明日志不包含密钥、Prompt 或模型输出。

## 2. OpenAI-compatible 调用接入

- [x] 2.1 将同步 Chat、结构化调用和 RAG 调用接入统一策略；测试 GLM 与 DeepSeek 均在瞬态失败后返回最终成功，并在不可重试 4xx 时只尝试一次。
- [x] 2.2 将流式 Chat 接入首 activity 前重试：失败流必须关闭，成功后只交付一次 activity 序列；首 activity 后的错误不得重试。
- [x] 2.3 调整 Interaction 的首 activity 等待窗口以容纳受限重试，并回归验证 SSE 字段、Conversation 写入与取消/关闭语义不变。

## 3. 验证与归档评估

- [x] 3.1 运行受影响 LLM、Conversation Runtime、Interaction SSE 和配置测试，覆盖 429、5xx、超时、预算止损与流式无重复写入。
- [x] 3.2 运行全量后端测试、架构边界测试、Ruff、编译、OpenSpec 严格校验和 `git diff --check`，修复本 Change 引入的问题。
- [x] 3.3 使用当前 GLM `resource` Profile 进行一次真实短流式 Chat 验收，确认正常调用不增加重试且 SSE 与会话持久化正确；汇总证据并评估是否达到归档标准。
