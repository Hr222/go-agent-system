## Why

当前重命名编辑器固定渲染在会话侧栏底部，和用户发起操作的会话项相隔较远。用户难以确认正在编辑哪一个会话，编辑器还会挤压侧栏的可见会话区域。

## What Changes

- 将重命名编辑器从侧栏底部移入被操作的会话项标题位置。
- 编辑时仅替换目标会话项的标题为输入框与保存、取消图标按钮，保留该项的日期、置顶标识和菜单入口。
- 保留既有话题概括更新接口、输入校验与失败保留草稿行为；保存或取消后恢复普通会话项展示。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `conversation-list-actions`: 调整 Chat 会话菜单的重命名交互，使编辑上下文与被操作会话项一致。

## Impact

- 影响 `frontend/src/features/chat/pages/ChatPage.tsx`、对应样式和组件交互测试。
- 不影响 HTTP 契约、持久化结构、服务端状态流转、主体隔离或置顶策略。
