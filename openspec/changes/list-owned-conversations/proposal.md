## Why

已知单个会话 ID 后可以读取历史，但用户无法发现自己已有的会话。需要提供主体范围内的轻量会话摘要列表，支撑历史会话入口。

## What Changes

- 新增按当前主体查询 Conversation 摘要的只读能力与 HTTP 接口。
- 摘要按最近更新时间倒序，包含恢复和展示所需的最小元数据。
- 不读取完整消息、不生成标题、不搜索正文、不修改会话。

## Capabilities

### New Capabilities

- `owned-conversation-list`: 定义主体范围内的会话摘要列表和游标分页行为。

### Modified Capabilities

无。

## Impact

- 影响 Conversation read port/repository、HTTP 查询契约与前端 API；不影响 LLM、消息写入或 Agent。
