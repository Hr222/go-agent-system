## Why

内联重命名已占用会话项标题区域，但同一项的“…”菜单仍显示。编辑期间菜单操作会与确认、取消形成竞争入口，也让紧凑的侧栏显得拥挤。

## What Changes

- 当会话处于重命名状态时，隐藏该会话项的“…”菜单按钮和菜单内容。
- 用户点击 `√` 保存成功或点击 `X` 取消后，恢复该会话项的“…”菜单入口。
- 保持其他会话项的菜单可用，且不改变现有重命名请求、错误处理或置顶行为。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `conversation-list-actions`: 明确重命名编辑状态下当前会话项的菜单可见性。

## Impact

- 影响 Chat 会话列表的 React 条件渲染和组件交互测试。
- 不影响 HTTP 契约、持久化、服务端状态、权限、安全或外部 Provider。
