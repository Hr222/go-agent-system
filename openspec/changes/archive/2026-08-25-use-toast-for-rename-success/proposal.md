## Why

会话重命名成功后，侧栏会新增一条长期可见的状态提示，打断用户继续浏览会话列表。该提示只确认一次已完成的操作，更适合使用 Ant Design 的瞬时全局成功浮层。

## What Changes

- 将 Chat 会话重命名成功后的反馈改为 Ant Design 成功浮层“会话名称已更新”。
- 重命名成功后不再写入侧栏的共享操作提示区域。
- 保留置顶和删除继续使用现有侧栏反馈，保留重命名失败时在目标会话项内的可重试状态。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `conversation-rename`: 明确重命名成功采用短暂的全局成功提示，且不占用侧栏共享状态区域。

## Impact

- 修改 `frontend/src/features/chat/pages/ChatPage.tsx` 中重命名成功分支。
- 修改 `frontend/src/features/chat/pages/ChatPage.list.test.tsx` 的 Ant Design 消息 mock 与成功反馈断言。
- 不改变 HTTP 接口、持久化数据、权限校验、状态流转或外部 Provider。
