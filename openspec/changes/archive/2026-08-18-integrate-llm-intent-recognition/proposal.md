## Why

通用 Embedding、能力目录、候选召回以及识别确认能力完成后，仍需一个统一入口把它们与前端确认、受控分发和现有 Agent/Online 用例组合起来，形成用户可使用的 LLM 意图识别流程。

## What Changes

- 新增统一交互 HTTP 契约和前端确认交互，展示识别结果、缺失资料、澄清问题和拟执行能力。
- 将统一交互作为 Chat 页面的内部路由层，用户不需要进入独立的意图识别工作台；只有需要执行能力时，才在对话流中看到确认卡片。
- 在用户明确确认后，由固定映射的 Controlled Dispatcher 分发到已登记的 Agent Runtime 或 Online 用例。
- 消费已归档的请求主体解析插口，将可信主体权限传入识别、确认和受控分发；当前匿名主体保持零权限。
- 保持现有直接 Chat、Agent、RAG 和知识库 HTTP 接口兼容，不强制既有调用先经过统一入口。
- 增加端到端验收、拒绝/取消路径和“未确认不执行”审计测试。

## Capabilities

### New Capabilities

- `llm-intent-recognition-gateway`: 将已完成的意图识别子能力组合为统一、待确认、受控分发的用户入口。

### Modified Capabilities

- 无。

## Impact

- 依赖并整合 `add-generic-embedding-port`、`add-platform-capability-catalog`、`add-intent-candidate-retrieval`、`add-structured-intent-recognition-confirmation` 和 `add-request-principal-resolver`。
- 影响 `modules/interaction`、HTTP 接口、前端交互、Composition Root 和端到端测试；不引入 Hermes、Fine-tune 或新的模型 Provider。
- 本 Change 不实现用户表、登录、角色管理、身份认证协议或请求主体解析器；它只消费已归档的请求主体解析边界。
