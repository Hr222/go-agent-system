## 1. 异步档案与安全契约

- [x] 1.1 在 Agent Management 定义服务端异步 Task 档案、档案注册 Port 与输入快照事实契约，固定能力代码、Task 提交策略和允许的展示摘要；不接受调用方 Task 参数。（`agent-task-bridge`：异步资格、固定提交档案）
- [x] 1.2 实现调用幂等键与输入快照指纹的确定性规范化，拒绝无效关联标识、不确定快照和不安全展示数据，且不记录原始输入。（`agent-task-bridge`：调用幂等、快照规范化失败）
- [x] 1.3 为档案、快照和幂等工具补充单元测试，覆盖有效配置、目录或类型不一致、非法字段和稳定输出。

## 2. Agent 到 Task 受控桥接

- [x] 2.1 实现仅依赖 `TrustedTaskSubmissionService` 的 Agent→Task 桥接 Application，使用可信主体、固定档案和快照事实提交 Task，并返回 opaque execution reference。（`agent-task-bridge`：受控排队任务、已接收引用）
- [x] 2.2 将 Task 提交拒绝、幂等冲突、快照失败和未配置依赖映射为稳定安全的执行失败；任何失败分支均不得返回部分引用。（`agent-task-bridge`：Task 提交失败）
- [x] 2.3 为桥接补充测试，覆盖成功提交、相同调用重放、同一调用不同输入冲突、未认证主体、档案缺失和快照失败，断言没有额外 Task/Event。

## 3. 执行策略与 Composition 组装

- [x] 3.1 实现由 Composition 固定配置的策略路由器：已登记异步能力使用桥接，其余能力继续使用同步策略；路由器不得成为动态注册或客户端可选执行器入口。（`agent-call-execution-strategy`：异步策略通过受控桥接）
- [x] 3.2 调整 `AgentCallDispatcher`、Composition Root 和导出边界以注入路由器，并保持现有目录/策略复核、错误投影、附件处理和同步调用兼容。（`agent-task-bridge`：授权失败先于桥接；`agent-call-execution-strategy`：同步策略不产生任务引用）
- [x] 3.3 为 Dispatcher 与 Composition 添加测试，覆盖授权前策略与桥接均未调用、异步能力返回 `accepted`、同步能力仍返回 `completed`，以及目录失效或档案不一致时不写入 Task。

## 4. 架构边界与验证

- [x] 4.1 增加架构边界测试，证明 interfaces、业务 Agent 和执行策略不直接导入 Task Repository/Lifecycle，且没有 HTTP、MCP 或 Function Calling 的通用 Task 创建入口。（`agent-task-bridge`：公开协议和同步路径隔离）
- [x] 4.2 更新 `ARCHITECTURE.md` 和系统看板中的实际实现状态与 Agent→Task 内部边界说明；不将 TM-07.4/07.5 的 Consumer、结果资源或 Workflow 写成已完成。
- [x] 4.3 执行相关 Agent、Task 与架构测试，随后执行 `ruff check app tests`、`python -m compileall -q app tests`、`openspec validate bridge-agent-calls-to-tasks --strict` 和 `git diff --check`；记录未能执行的验证原因。
