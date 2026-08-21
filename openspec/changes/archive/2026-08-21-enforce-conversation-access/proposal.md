## Why

仅保存 `owner_subject` 不能阻止调用方按任意 UUID 读取或写入会话。需要把主体和会话 ID 的校验固化为 Conversation 应用边界，供后续 HTTP、Dialogue 和附件链路复用。

## What Changes

- 新增 Conversation Access 应用契约，按可信主体创建或解析已准入会话。
- 所有通过该契约的读取、追加和事件访问必须以 `owner_subject + conversation_id` 校验。
- 对不存在和不属于当前主体的会话返回相同的受控拒绝结果。
- 不新增 HTTP 路由、用户模块、角色授权或模型调用。

## Capabilities

### New Capabilities

- `conversation-access`: 定义主体范围内的 Conversation 创建、解析和拒绝行为。

### Modified Capabilities

无。

## Impact

- 影响 Conversation application/ports/repositories、Dialogue 与 Agent 调用的组装入口。
- 影响资源访问安全；不改变 `RequestPrincipal` resolver 和外部 Provider。
