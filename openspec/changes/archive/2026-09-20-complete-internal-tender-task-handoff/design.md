## Context

内部 Dialogue 已可通过受信任 Agent→Task 桥接创建 Tender Task，Task Worker、恢复和重试 Application 也已有单次执行契约。但系统没有可部署的 Worker 运行入口；HTTP 的 FastAPI lifespan 也不应承担后台执行职责。另一方面，`AgentExecutionOutcome.accepted` 是 Dispatcher 的合法结果，Dialogue 轮次却只识别完成、取消、拒绝和失败，导致已创建的 Task 被错误投影为失败。

外部 Tender MCP 已恢复为独立同步 Dispatcher，必须保持请求内的 `EmbeddedResource` 协议。本 Change 仅处理内部 Dialogue 到 Task 的交接，不改变该边界。

## Goals / Non-Goals

**Goals:**

- 提供由运维显式启动的 Tender Task Worker 进程，持续运行既有恢复、重试和执行单次循环，并为每个循环阶段释放数据库资源。
- 将 `accepted` 作为 Dialogue 和 Chat 确认的有效状态，向当前主体返回安全的 `execution_reference`，并以既有 `agent_call` 会话事件记录该状态。
- 保持 Task 生命周期、主体隔离、固定 Task 类型和外部 MCP 同步协议不变。

**Non-Goals:**

- 不在 FastAPI 进程中启动 Worker，不新增浏览器 Task 创建、Task 结果下载、任务页面或实时推送。
- 不将 Task 终态自动写回 Conversation，不调用 Continuation 生成异步完成消息。
- 不实现 Workflow、SubAgent、动态执行器注册或新的编排框架。

## Decisions

### 1. 使用独立进程运行既有单次调度能力

新增 `python -m app.run_tender_task_worker` 入口。进程按受配置约束的间隔依次运行 lease 恢复、重试重入队和一次 Tender Worker 领取；每个阶段使用独立 Session 和 Composition Root，完成后关闭资源。该入口只固定 `tender.generate_bid_skeleton` Executor，不能从命令行或环境选择任意 task type、执行器或主体。

不将循环放进 FastAPI lifespan：开发 reload、多个 HTTP 副本和请求进程重启都会导致无法控制的重复 Worker。也不引入队列框架或新守护服务；现有 PostgreSQL 原子领取、lease 与恢复契约已经处理多个 Worker 的竞争与崩溃恢复。

### 2. `accepted` 是调用交接状态，不是终态失败

Dialogue Invocation 在 Dispatcher 返回 `accepted` 时追加一个 `agent_call` 状态事件，载荷仅含 `status: accepted` 与 `execution_reference`。它不追加 `agent_result`、`agent_error` 或 assistant Message。Dialog Agent Turn、Gateway 和 HTTP response 透传 `accepted`，将引用作为安全 `execution_result` 对象返回。

使用已有 `agent_call` 事件而不增加新的 Conversation Event 类型：接受态描述的是同一调用从“待确认”转为“已交给内部执行”的状态变化，不是新的业务结果。同步完成与失败的事件语义保持不变。

### 3. 本 Change 不建立 Task 到 Conversation 的终态回传

Worker 成功后继续只写 Task 的安全摘要、指纹与生命周期事件；用户或内部调用方可使用既有主体隔离的 Task 查询契约观察状态。自动生成 Conversation 终态事件、通知或续写需要独立的回收/编排设计，因为它必须定义重复投递、会话删除、用户取消和 Task 重试后的唯一终态语义。

## Risks / Trade-offs

- [独立进程未部署] → 启动命令和配置写入 README；运行入口记录受控错误并继续下一轮，部署仍需由运维启动。
- [循环内 Provider 调用阻塞] → 每次领取最多执行一个 Task，且执行结束即关闭该阶段 Session；lease、取消和恢复仍使用既有边界。
- [同一 Task 被多个 Worker 看见] → 继续依赖 PostgreSQL 原子领取与 lease，而非进程内互斥。
- [Chat 误报异步任务已完成] → `accepted` 与 `completed` 保持不同状态；响应只返回执行引用，绝不返回假结果或下载资源。

## Migration Plan

1. 部署应用代码后，按配置单独启动 Tender Worker；现有 HTTP 与 MCP 进程不需要迁移。
2. 未启动 Worker 时，内部调用仍会安全地停留在 `queued`，不会改变外部 MCP 行为。
3. 回滚时停止新 Worker 进程；已领取的任务由既有 lease 到期恢复流程处理，未领取的任务保持 `queued`。不需要数据迁移。

## Open Questions

- 无。本 Change 明确不包含 Task 终态的 Conversation 回传；该能力在需要用户可见异步完成通知时另行立项。
