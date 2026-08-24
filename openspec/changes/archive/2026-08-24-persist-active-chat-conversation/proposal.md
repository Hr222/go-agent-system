## Why

浏览器在得到 `conversation_id` 后仍只保存在页面内存，刷新会丢失当前会话。先持久化当前选择，才能在下一步安全恢复历史。

## What Changes

- Chat 前端在创建会话或收到服务端会话标识后保存当前 `conversation_id`。
- “新建对话”清除当前选择；无效或访问被拒绝的会话标识也必须清除。
- 不加载消息历史、不增加会话列表 UI、不自行生成 UUID。

## Capabilities

### New Capabilities

- `active-chat-conversation-state`: 定义浏览器当前 Conversation 标识的恢复性本地状态。

### Modified Capabilities

无。

## Impact

- 仅影响 React Chat 状态、流式元数据类型和前端测试；不改变后端或存储事实。
