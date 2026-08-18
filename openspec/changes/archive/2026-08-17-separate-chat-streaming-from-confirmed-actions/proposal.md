## Why

当前 Chat 将普通技术问答识别为 `chat.general` 后，仍按“必须批准”的路径处理；用户必须为一次无副作用的模型回答点击批准。同时，Chat 页面改用完整 JSON 交互响应后，不再消费既有 SSE 增量，回答失去真实流式展示。

需要把低风险对话与会产生业务动作的能力分开：前者由服务端受控放行并流式回答，后者继续由用户明确批准。

## What Changes

- 为能力目录中的确认策略定义实际分流语义：`never` 表示无需用户批准的受控执行，`always` 保持显式批准；首版将 `chat.general` 调整为 `never`。
- 新增服务端控制的交互流式入口。它先完成候选召回、结构化识别、权限过滤和策略判断；低风险普通对话才进入 Chat SSE 输出，需批准的能力返回受控批准状态而不执行。
- Chat 页面改为消费该交互流：普通对话恢复真实逐增量展示；澄清和失败显示为对话消息；需业务执行时显示现有批准卡。
- 保留既有 `/api/v1/llm/chat` 和 `/api/v1/llm/chat/stream` 契约，作为兼容接口，不让浏览器根据文本自行选择是否调用能力。
- 不为 Agent、知识检索或其他确认后执行的能力补做流式执行；它们在批准后仍可先返回受控完整结果。

## Capabilities

### New Capabilities

- `risk-tiered-chat-interaction`: 服务端完成风险分流，并为无需批准的普通 Chat 提供受控流式响应。

### Modified Capabilities

- `platform-capability-catalog`: 确认策略成为目录条目的可执行分流规则，而不仅是描述字段。
- `llm-chat`: 既有直接 Chat 契约保持兼容；平台 Chat 页面改由服务端控制的交互流驱动其普通对话输出。
- `explicit-capability-confirmation`: 仅为确认策略要求批准的已匹配能力创建提议。

## Impact

- 影响 `modules/interaction`、Interaction HTTP Route/Schema、Composition Root、能力目录种子与迁移，以及 Chat 前端的请求状态和 SSE 解析。
- 新增的流式入口会暴露受控事件类型，但不会向浏览器暴露分发键、完整输入、Provider 对象或执行器。
- 不改变模型 Provider 配置、认证方案、现有直接 Chat HTTP 接口，亦不放宽 Agent、文件、外部调用或写入类能力的显式批准要求。
