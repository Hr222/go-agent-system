## Why

P2.4 已固定了不携带执行权的 `StructuredAgentCall` 数据契约，但结构化对象本身不能证明能力存在、输入合法、当前主体有权限或用户已经批准。P2.5 需要把这些确定性策略集中到独立校验边界，为后续受控分发提供可解释的授权结果。

## What Changes

- 新增 Agent Call 策略校验服务，按平台能力目录重新读取并确认目标是已启用且可调用的 Agent 能力。
- 对结构化调用执行目录输入 Schema、当前主体权限和 Agent 类型校验；目录不可用时返回受控失败，不放宽边界。
- 根据目录确认策略返回“已授权”或“需要确认”；`conditional` 在没有独立条件规则时按 `always` 处理。
- 对传入的已确认提议执行能力代码、固定分发键和输入快照匹配校验；不匹配的提议不得转化为授权结果。
- 增加策略分支、权限、输入、提议匹配和无执行副作用测试。

## Capabilities

### New Capabilities

- `agent-call-policy-validation`：校验结构化 Agent Call 的目录、权限、输入和确认策略，并返回受控授权状态。

### Modified Capabilities

- 无。

## Impact

- 新增 `app/modules/interaction/application/agent_call_policy.py` 及应用层导出和测试。
- 不新增 HTTP 路由、数据库表、Redis、Conversation 事件、LLM Provider 或 Agent Runtime 调用。
- 不消费或修改 P2.3 的待确认提议存储；只接受确认层产出的受信 `ApprovedCapabilityDispatch` 作为匹配输入。
- 不修改现有 V1 `IntentInteractionGateway` 和 `ControlledDispatcher`；P2.6 再将策略结果接入受控分发。
