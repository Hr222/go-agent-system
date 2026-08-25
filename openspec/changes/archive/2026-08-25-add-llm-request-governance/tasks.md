## 1. Provider 配额配置

- [x] 1.1 为 GLM resource、Coding Plan 和 DeepSeek 定义经校验的 RPM、burst、并发上限配置，并将有效配置暴露给 Provider Client Factory。
- [x] 1.2 删除仅在 HTTP 流式入口生效的旧并发配置与状态，更新 `.env.example` 的迁移说明。
- [x] 1.3 覆盖默认值、Profile 隔离、通用 Provider 配置和无效配置的自动化测试。

## 2. 基础设施请求治理器

- [x] 2.1 在 `infrastructure/llm` 实现线程安全、可取消的令牌桶与并发租约，并记录脱敏等待日志。
- [x] 2.2 验证速率等待、突发限制、同步和异步并发释放、取消等待以及配置边界。

## 3. 适配器接入

- [x] 3.1 由共享 OpenAI-compatible Client Factory 创建并向 Chat、Structured 和 RAG 适配器注入同一治理器。
- [x] 3.2 让同步 Chat、结构化调用和 RAG 的每次重试都在真实 Provider 调用前取得治理租约。
- [x] 3.3 让流式 Chat 在每次尝试取得租约、在关闭或失败时释放，并验证首 activity 前重试重新计入配额。

## 4. 验证与归档准备

- [x] 4.1 运行受影响的单元测试、架构测试、Ruff 和编译检查，修复本 Change 引入的问题。
- [x] 4.2 运行全量后端测试、OpenSpec 严格校验与 `git diff --check`，记录结果。
- [x] 4.3 在 resource Profile 下进行一次受限真实流式验收，确认请求正常完成且日志不泄露敏感数据；无法安全执行时记录明确原因。
