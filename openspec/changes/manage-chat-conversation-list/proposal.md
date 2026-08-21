## Why

Chat 侧栏当前是静态空列表。用户需要从已归属的会话摘要中选择会话，才能在多个历史对话之间高效切换。

## What Changes

- 使用主体范围会话列表 API 替换静态侧栏数据。
- 支持选择一个会话、保存其为当前会话并触发既有历史加载；新建操作调用既有创建接口。
- 覆盖加载、空列表和失败重试，不实现正文搜索、删除、重命名或标题生成。

## Capabilities

### New Capabilities

- `chat-conversation-list-management`: 定义 Chat 侧栏查询、创建和切换历史会话的前端行为。

### Modified Capabilities

无。

## Impact

- 影响 Chat feature 与前端测试；依赖已完成的会话创建、摘要列表、当前会话状态和历史加载能力。
