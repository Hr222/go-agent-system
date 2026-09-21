## Why

当前仓库已经具备能力目录、受控 Agent Dispatcher、内部 Task 和独立 Tender Worker，但 Workflow 仍只有前端 mock，没有服务端可评审的运行事实或节点契约。现在直接实现完整编排器会把 Workflow、Task、Dialogue 和多 Agent 责任混在一起；需要先定义一条稳定、可验证的 Workflow 边界，作为后续真实编排和多 Agent Change 的基础。

## What Changes

- 新增 Workflow Definition 与不可变 Version 的平台契约，明确节点、边、输入输出引用和固定能力绑定。
- 新增 Workflow Run 与 Node Run 的状态、事件、幂等、取消、失败和重试语义；Run/Node 事实与 Task 生命周期保持分层，不把 Task 状态直接当作 Workflow 状态。
- 只允许服务端固定的 `capability` 节点引用 Platform Capability Catalog 中已启用且可授权的能力；节点执行复用既有 Dispatcher/Task 边界，不接受 URL、Python 类名、任意 Executor 或客户端分发键。
- 为第一阶段提供受信任 Application/Port 契约和内存验证替身，使用 Tender 能力作为节点绑定测试样本，但不新增 Tender 专属编排逻辑。
- 保持现有外部 Tender MCP 同步、内部 Dialogue `accepted + execution_reference`、Task Worker 和 Task 结果查询语义不变。
- **不在本 Change 实现**浏览器 Workflow 编辑器、公开 Workflow HTTP 创建/执行入口、动态 DAG 执行器、SubAgent、多 Agent 协同、Task 结果下载或 Task 终态 Conversation 回传。

## Capabilities

### New Capabilities

- `workflow-run-and-node-contracts`: 定义 Workflow Definition/Version、Run/Node Run 及固定能力节点的受信任生命周期契约。

### Modified Capabilities

- 无。现有 `platform-capability-catalog` 已规定后续编排必须消费目录；本 Change 通过新 Workflow 能力落实该约束，不改变目录本身的要求。

## Impact

- 影响 `app/platform` 下新增的 Workflow Domain、Application 和 Ports，以及 Composition 中的固定绑定和测试替身。
- 可能新增 Workflow 生命周期持久化模型与迁移，但不修改现有 Task、Conversation 或 Agent Call 持久化结构；具体是否落 PostgreSQL 由 design 和任务阶段确定，不能把未实现的持久化声称为完成。
- 不新增公开 HTTP/MCP/Function Calling 路由，不改变现有浏览器响应字段或外部 Provider 契约。
- 安全边界要求 Workflow 输入、节点参数、执行引用和错误事件不保存凭据、原始文件、lease、Provider 原文或任意可执行地址；节点授权仍以可信主体和能力目录为准。
