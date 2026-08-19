## Why

P2.5 已经能够判断一个结构化 Agent 调用是否满足目录、权限、输入和确认策略，但目前还没有面向 V2 调用契约的执行边界。若没有独立的分发服务，后续 Dialogue Runtime 只能直接依赖旧的 V1 Dispatcher，容易把未授权调用、目录分发键或执行器细节带入对话层。

## What Changes

- 新增面向 `StructuredAgentCall` 的 Agent 分发应用服务。
- 分发前调用 `AgentCallPolicyValidator`；只有 `authorized` 结果可以进入 Agent Runtime。
- 根据当前能力目录重新取得固定 `dispatch_key`，由 Composition Root 提供受控的 Agent Runtime 入口，不接受模型或客户端提供的执行地址。
- 将 Agent Runtime 的对象结果转换为 `AgentCallResult`，将策略失败、目标不可用、输入异常和执行异常转换为 `AgentCallError`。
- 为未授权、确认缺失、目录不可用、目标缺失、输出非法和执行失败增加可验证的单元测试。

## Capabilities

### New Capabilities

- `controlled-agent-dispatch`：在策略授权后通过固定 Agent Runtime 映射执行结构化 Agent 调用。

### Modified Capabilities

- 无。

## Impact

- 新增 `app/modules/interaction/application` 中的 V2 Agent 分发服务及其导出，必要时在 `app/composition/` 增加装配函数。
- Agent Runtime 继续从平台能力目录读取当前 Agent 条目；不会新增平行能力注册表或执行地址字段。
- 不新增或修改 HTTP 接口、Conversation 持久化、数据库表、Redis、前端协议、重试机制、SubAgent 或 Workflow 编排。
- 现有 V1 `ControlledDispatcher`、`IntentInteractionGateway` 和 `/api/v1/llm/chat` 保持兼容，后续 Dialogue 链路再消费本 Change 的服务。
