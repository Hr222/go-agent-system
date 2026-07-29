## Why

当前流式 Chat 已能接收 SSE `delta` 事件，但同一读取批次内的多次状态更新会被 React 合并，且界面没有持续输出提示。模型在首片段后快速返回时，用户只能看到最终答案，无法确认前端正在逐步消费流式内容。

这既削弱了流式交付的用户价值，也让排障时难以区分首片段慢、上游超时和页面未渲染。

## What Changes

- 将流式 HTTP 客户端收敛到 `services/http`，保留 `fetch` 与 `ReadableStream` 作为 POST SSE 的受控例外。
- 在 Chat 页面增加按动画帧提交的增量渲染队列，保证已接收的 `delta` 不会因 React 批处理而只呈现最终文本。
- 为连接中和输出中提供明确、持续可见的状态提示；完成、取消和失败时正确清理待渲染内容并保留已显示文本。
- 增加前端测试，覆盖同一 SSE 读取批次、多帧增量、完成前排空队列及失败、取消的状态边界。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `llm-chat`：前端必须以用户可感知的方式逐步展示已接收的流式增量，并在整个请求生命周期内展示准确状态。

## Impact

- 影响 `frontend/src/services/http`、`frontend/src/features/chat/api`、`frontend/src/features/chat/hooks` 与 Chat 页面样式和测试。
- 不修改 `/api/v1/llm/chat/stream` 的 HTTP 路径、SSE 事件、字段或后端 Provider 调用。
- 不新增持久化、会话历史、Agent 编排、外部依赖或敏感数据处理。
