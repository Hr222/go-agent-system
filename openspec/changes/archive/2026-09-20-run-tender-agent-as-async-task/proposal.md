## Why

TM-07.3 已经能把登记过的 Agent 调用受控提交为 Task，但还没有业务 Consumer 领取并执行任务。Tender 的 `generate_bid_skeleton` 是当前最适合验证异步链路的长耗时能力；本 Change 将它接入既有 Task Worker，同时保留主体隔离、取消、重试和未来多 Agent/Workflow 扩展的端口。

## What Changes

- 为 `agent.tender.generate_bid_skeleton` 注册服务端固定的异步 Task 档案和 `tender.generate_bid_skeleton` Task 类型。
- 为 Tender 定义受控输入快照端口与持久化适配器，保存文件引用、文件名、内容摘要和用户焦点，不把原始输入写入 Task Event 或 HTTP 投影。
- 将 TM-07.3 的桥接结果传递给 Worker 所需的 opaque 快照引用，并保持同步能力与未登记能力的既有行为。
- 增加固定的 Tender Task Executor：按主体读取快照、调用既有 `TenderApplication`，支持租约续期和协作式取消，并将成功/失败转换为安全 Task 结果。
- 在 Composition Root 提供 Tender 异步路由、快照存储和 Worker 的显式绑定；不新增公开 Task 创建、领取或结果写回接口。
- 补充成功、快照缺失、主体越权、取消、可重试失败、幂等重放和执行器固定绑定测试，并同步实际进度文档。

## Capabilities

### New Capabilities

- `tender-async-task-execution`: 定义 Tender 指定 Agent 能力如何通过受控 Task 快照和固定 Worker Executor 异步执行。

### Modified Capabilities

- `agent-task-bridge`: 异步快照事实中的 opaque 引用必须进入内部 Task 执行上下文，但不得进入公开 Task 投影或事件元数据。

## Impact

- 影响 `app/business/agents/tender` 的快照端口和 Task Executor、`app/platform/interaction` 的桥接传递、`app/platform/task` 的内部执行上下文，以及 `app/composition` 的固定组装。
- 复用既有 Task 状态机、Worker、恢复、取消、重试和主体隔离；不改变 Task HTTP 契约，不新增数据库表或公开协议入口。
- 快照正文由服务端受控存储保存，运行时文件只进入 `.runtime/`；Task 只保存安全指纹和 opaque 引用。
- 不实现 TM-07.5 的结果资源映射，不把 Tender 变成平台级能力，也不引入 LangGraph、Workflow 或动态 Executor 注册。
