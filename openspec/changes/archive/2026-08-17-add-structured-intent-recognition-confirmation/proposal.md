## Why

候选召回只缩小范围，仍需要从用户输入中判断目标能力、提取资料并处理不确定情况。同时系统必须在任何业务能力执行前获得用户明确确认。

## What Changes

- 新增基于候选集的 Structured LLM 意图识别用例，返回受约束的能力代码、已提取输入、缺失输入和澄清信息。
- 新增确认提议模型和确定性规则，处理确认、取消、无候选、能力禁用、输入缺失和权限不满足。
- 让该用例仅产生待确认提议，不调用 Agent、RAG、政策判断或其他业务能力。
- 不新增 HTTP/前端交互、跨会话确认持久化、任务状态机或自动分发。

## Capabilities

### New Capabilities

- `structured-intent-recognition`: 在已召回的候选范围内识别意图并返回结构化结果。
- `explicit-capability-confirmation`: 管理一次显式确认所需的待执行提议与取消边界。

### Modified Capabilities

- 无。

## Impact

- 依赖候选召回和现有 Structured LLM Port；新增 `modules/interaction` 的应用与领域契约。
- 不改现有直接 HTTP 调用链，不允许 LLM 直接执行能力。
