## Why

前端已经按动画帧渲染 SSE 增量，但真实 GLM 常在首片段后集中返回较大的文本块，用户仍会感觉回答一次性出现。需要在不改变模型传输和答案内容的前提下，增加受控的展示节奏，让已接收文本持续、可感知地出现。

## What Changes

- 将助手消息的渲染队列改为按可读文本单元逐步提交，而不是直接显示整个 Provider `delta`。
- 为积压内容设置有界加速策略，避免快速流或流结束后因展示动画造成长时间延迟。
- 保持连接、输出、完成、取消和失败的现有语义；终止状态继续等待本地展示队列排空。
- 增加文本单元顺序、展示节奏和快速排空的前端测试与浏览器验收。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `llm-chat`：流式 Chat 的前端展示从按 Provider 片段追加调整为用户可感知的受控逐步输出，并保持最终文本完整、顺序不变。

## Impact

- 影响 `frontend/src/features/chat/hooks/useDeltaRenderQueue.ts`、Chat 页面及其测试。
- 不修改 HTTP 路径、SSE 事件、Provider 调用、模型内容、持久化或外部依赖。
- 不记录或发送额外的用户内容，不改变错误、取消与重试的安全边界。
