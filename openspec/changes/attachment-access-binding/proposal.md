## Why

动态附件如果只有随机 ID 而没有访问绑定，持有 ID 的其他主体可能读取文件。附件需要与可信主体或会话绑定，并支持 TTL 与一次性消费，以适配未来多种文件 Agent。

## What Changes

- 为附件记录创建主体和可选会话绑定。
- 读取、消费和删除操作执行主体校验。
- 明确过期和一次性消费状态。

## Capabilities

### New Capabilities

- `attachment-access-binding`: 附件主体隔离、会话绑定和生命周期访问控制。

### Modified Capabilities

- 无。

## Impact

影响附件元数据存储和读取 Port；不实现用户模块，不改变现有匿名权限解析，也不涉及 Agent 编排。

