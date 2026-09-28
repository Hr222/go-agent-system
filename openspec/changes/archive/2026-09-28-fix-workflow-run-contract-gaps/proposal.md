## Why

当前 Workflow 实现能够创建并推进基本的 Run/Node 状态，但三条关键边界仍与既有规格不一致：不可重试的输入错误会让 Run 停留在 `queued`，取消只更新本地状态而不通知实际执行器，依赖节点的输入仍可由调用方直接伪造。继续在此基础上接入调度或异步执行会放大状态不一致和数据流完整性风险。

## What Changes

- 将节点输入、权限和能力契约校验失败记录为稳定的 Node Run/Run 失败事实，不创建执行尝试或 Task。
- 为 Node Executor 增加受控的协作取消端口，并在取消运行中节点时调用该端口。
- 为 Workflow 运行时保存并校验节点输出事实，使有边依赖的节点只能消费前置节点实际产生的安全输出字段。
- 为上述边界补充领域、Application 和 Port 的自动化测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `workflow-run-and-node-contracts`：收紧输入失败、协作取消和节点输出依赖的运行时契约。

## Impact

- 影响 `app/platform/workflow` 的 Domain、Application 和 Executor Port，以及对应的内存测试替身和持久化映射。
- 影响 Workflow Run/Node Run 的状态流转和安全事件，但不新增公开 HTTP/MCP/Function Calling 契约。
- 不改变现有数据库表结构；输出事实使用现有安全摘要/指纹边界，原始输入、Provider 响应和凭据仍不得持久化。
- 外部执行器需要实现新的协作取消方法；当前尚无生产 Workflow Executor，因此不会产生现有 Provider 迁移。
