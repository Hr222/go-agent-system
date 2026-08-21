## Why

后端历史 HTTP 契约存在后，Chat 页面仍需把当前会话标识转换为可展示的真实消息。该行为应与会话列表和上下文运行时解耦，便于独立验证恢复链路。

## What Changes

- Chat 前端在有保存的当前会话 ID 时加载并分页渲染消息历史。
- 加载、空会话、访问拒绝和网络失败提供明确状态；访问拒绝时清除本地当前会话选择。
- 不实现侧栏会话列表、搜索、标题生成或模型上下文逻辑。

## Capabilities

### New Capabilities

- `chat-conversation-history-loading`: 定义 Chat 页面恢复当前会话消息的前端行为。

### Modified Capabilities

无。

## Impact

- 影响 Chat feature、React Query/API 类型和前端测试；依赖已存在的历史 HTTP 接口。
