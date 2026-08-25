## Why

置顶、取消置顶和删除成功后，Chat 仍会在侧栏顶部占用一行显示共享状态条。重命名已经采用 Ant Design 全局成功浮层，继续保留其他成功操作的侧栏状态条会造成同类反馈表现不一致，并挤压会话列表空间。

## What Changes

- 将置顶成功提示改为 Ant Design 全局成功浮层“已置顶会话”。
- 将取消置顶成功提示改为 Ant Design 全局成功浮层“已取消置顶”。
- 将删除成功提示改为 Ant Design 全局成功浮层“会话已删除”。
- 移除侧栏共享成功提示状态及其渲染区域。
- 保留置顶失败、删除失败、列表加载失败和删除确认的现有交互。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `conversation-list-actions`: 置顶、取消置顶和删除成功反馈统一使用 Ant Design 全局成功浮层，不再显示侧栏共享成功状态条。

## Impact

- 修改 `frontend/src/features/chat/pages/ChatPage.tsx` 中置顶、删除成功分支及侧栏渲染。
- 修改 `frontend/src/features/chat/pages/ChatPage.list.test.tsx` 的成功消息 mock 与置顶/删除成功断言。
- 更新 `conversation-list-actions` 主规格。
- 不改变 HTTP 契约、数据库、持久化事实、权限边界或外部 Provider。
