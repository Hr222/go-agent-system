## 1. OpenAI-compatible 客户端组装

- [x] 1.1 让 `OpenAICompatibleClientFactory` 懒创建并缓存 `AsyncOpenAI`，且与同步 Client 使用同一 Provider 端点、密钥、超时和 `max_retries=0`；用替身测试验证 GLM 与 DeepSeek 配置。
- [x] 1.2 创建 `ChatOpenAI` 时显式注入 Factory 管理的同步和异步 Completion Client，并保持 `max_retries=0`；测试流式模型不会由 LangChain 自行创建异步 Client。
- [x] 1.3 为 Factory 提供可等待的异步关闭操作，在已创建异步 Client 时调用其关闭接口；测试关闭行为不影响仅使用同步 Client 的现有路径。

## 2. Container 生命周期

- [x] 2.1 为 `ApplicationContainer` 提供异步资源清理入口，并在全局 FastAPI lifespan 关闭时等待执行；测试全局 Container 的异步 Client 能被释放。
- [x] 2.2 调整请求级 Container dependency，使普通响应、SSE 正常结束和 Generator 关闭后才等待异步清理；测试清理不改变既有 SSE 事件内容。

## 3. 回归验证

- [x] 3.1 运行受影响的 LLM Factory、Composition Root 和 HTTP 流式生命周期测试，确认 GLM 与 DeepSeek 都保持 Provider-neutral 行为。
- [x] 3.2 运行后端测试、架构边界检查、Ruff 与编译检查，修复本 Change 引入的问题且不掩盖既有问题。
- [x] 3.3 运行 OpenSpec 严格校验与 `git diff --check`，确认规格、设计、任务和实现一致。

## 4. 人工验收与归档评估

- [x] 4.1 使用现有 GLM 资源包 Profile 完成一次真实流式 Chat，确认请求结束、会话持久化和 SSE 事件保持正常，并记录验收证据。
- [x] 4.2 汇总验证结果，判断 Change 是否达到归档标准；达到时同步正式规格、归档并以中文提交，否则说明未归档原因。
