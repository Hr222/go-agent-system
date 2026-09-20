## 1. 桥接与 Task 执行上下文

- [x] 1.1 扩展 Agent→Task 桥接，将快照事实中的 `snapshot_reference` 和白名单关联字段交给受信任提交能力；保持 TaskView、事件和公开分发结果不暴露内部引用（对应 `agent-task-bridge` 修改需求）。
- [x] 1.2 为受信任 Worker 的 `TaskExecutionContext` 增加可信 owner 主体，并补充架构测试证明 Executor 只能通过上下文和生命周期回调工作（对应 Tender Executor 需求）。

## 2. Tender 快照与结果端口

- [x] 2.1 在 `app/business/agents/tender` 定义异步输入快照、结果保存和 Executor 所需的最小 Ports/契约；拒绝原始输入、非附件输入和不安全元数据。
- [x] 2.2 实现基于现有 AttachmentStoragePort 的 Tender 快照 Provider，校验主体、会话、文件名、媒体类型和 sha256，并生成稳定指纹。
- [x] 2.3 实现仅写入 `.runtime/` 的结果存储适配器和测试替身；结果以 task_id 幂等保存，不提供 HTTP/MCP 下载入口。

## 3. Tender Task Executor

- [x] 3.1 实现固定 `tender.generate_bid_skeleton` Executor：读取主体绑定快照、调用既有 TenderApplication、保存内部结果并返回安全结果指纹与摘要。
- [x] 3.2 接入取消检查和 lease 续租回调；将输入/解析/配置错误、上游暂时错误和取消分别映射为安全的不可重试、可重试或协作取消结果。
- [x] 3.3 为 Executor 补充单元测试，覆盖成功、快照缺失、越权、取消、上游重试、结果幂等和敏感数据不泄漏。

## 4. Composition 与异步路由

- [x] 4.1 在 Composition Root 固定注册 Tender 异步档案、快照 Provider、受信任提交服务、结果存储和 task type Executor；未配置依赖时不得隐式降级为同步执行。
- [x] 4.2 将 Tender 异步路由接入 AgentCallDispatcher，同时确认其他 Tender 能力和普通 Agent 能力仍使用同步策略。
- [x] 4.3 增加跨模块测试，覆盖授权后 accepted、Task Worker 完成/失败/重试、主体隔离和无公开创建入口。

## 5. 文档与验收

- [x] 5.1 更新 `ARCHITECTURE.md`、系统看板和必要的模块导出，准确记录 TM-07.4 已实现范围，不声明 TM-07.5、前端或 Workflow 已完成。
- [x] 5.2 执行相关 pytest、架构边界测试、`ruff check app tests`、`python -m compileall -q app tests`、`openspec validate run-tender-agent-as-async-task --strict` 和 `git diff --check`，记录可复现验证结果。
