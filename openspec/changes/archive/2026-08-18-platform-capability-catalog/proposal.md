## Why

V2 的 Interaction Gateway、后续受控 Agent 调用和现有 Agent Runtime 都需要从同一处获得“平台当前允许调用什么能力”的事实。仓库已经具备 `platform_capability` 表、领域模型和只读目录服务，但它们产生于旧交互链路；P2.1 需要将其明确收敛为 V2 的能力目录基线，避免后续识别、确认或运行时重新建立平行注册表。

## What Changes

- 将现有 `platform_capability`、`PlatformCapability`、`CapabilityCatalogPort` 与只读目录服务确认为 V2 的平台能力目录基线。
- 固化目录的职责：保存能力描述、输入输出契约、权限、确认策略、启用状态、超时、错误边界、检索元数据和受控 `dispatch_key`；只返回已启用且当前主体有权限访问的条目。
- 固化目录与后续模块的边界：目录不识别自然语言、不创建确认提议、不授权调用、不执行 Agent 或其他 Use Case；Gateway、Agent Runtime 和后续编排能力只能通过目录端口消费条目。
- 补充针对该边界的回归验证，确认任何能力类型均可被统一描述，而 Agent Runtime 仅消费其中的 `agent` 条目。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `platform-capability-catalog`：补充 V2 下目录的唯一事实来源和消费边界；不改变已有目录字段、HTTP 契约或实际分发行为。

## Impact

- 影响 `app/modules/interaction` 的目录领域、端口和应用服务，以及 `app/modules/agent/runtime` 的目录消费边界。
- 复用既有 PostgreSQL `platform_capability` 表、持久化 Repository、受控种子数据和 Composition Root，不新增迁移、缓存、HTTP 路由或前端界面。
- 后续 `interaction-candidate-recognition`、`interaction-proposal-confirmation`、`structured-agent-call-contract` 和 `controlled-agent-dispatch` 以此为前置依赖；它们分别负责识别、确认、调用契约和实际执行。
