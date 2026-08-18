## Why

现有 LLM Chat 是无状态的单轮调用，项目没有能够稳定保存和恢复会话消息的领域模型或持久化结构。后续多轮对话、上下文构建和 Agent 结果回填都依赖这一基础；先单独完成模型与存储边界，才能避免后续 Change 反复调整表结构。

## What Changes

- 新增 `Conversation` 与 `Message` 的最小领域模型，明确会话标识、消息标识、角色、内容、顺序和创建时间的含义。
- 新增 Conversation 与 Message 的 PostgreSQL 表、外键、唯一性和基础数据约束，并提供与现有 `sql/` 顺序脚本一致的初始化脚本。
- 新增 SQLAlchemy ORM 持久化模型及模型注册，使测试和后续 Repository 可以使用同一套表映射。
- 为后续 Repository 建立领域对象与持久化记录之间的转换边界；本 Change 不提供创建会话、追加消息或读取历史的应用服务与 HTTP 接口。
- 不修改现有 `/api/v1/llm/chat`、LLM Provider、Agent Runtime、Interaction Gateway 或前端调用。

## Capabilities

### New Capabilities

- `conversation-model-storage`：保存 Conversation 与 Message 基础记录，并以数据库约束保护会话归属、消息角色和消息序号的持久化完整性。

### Modified Capabilities

- 无。

## Impact

- 新增 `app/modules/conversation/domain/` 下的最小领域模型，以及后续 Repository 可复用的转换边界。
- 新增 `app/infrastructure/persistence/models/` 下的 Conversation ORM 模型，并更新模型注册。
- 新增一份 PostgreSQL 初始化脚本；不修改既有知识库表和平台能力目录表。
- 新增 ORM 映射、约束和迁移脚本测试；不引入 HTTP 契约、外部 Provider、安全主体或前端变更。
