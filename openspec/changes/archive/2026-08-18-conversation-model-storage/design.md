## Context

当前 `modules/llm` 只接受单轮 `ChatLlmRequest`，没有会话 ID、消息历史或持久化模型。V2 的 `Dialogue Runtime`、Context Builder 和 Agent 调用结果回填都需要一组可长期保存、可按顺序恢复的 Conversation 基础记录。

项目现有持久化采用 PostgreSQL、SQLAlchemy ORM 和按编号维护的 `sql/*.sql` 脚本。测试通过隔离 PostgreSQL schema 执行 `Base.metadata.create_all()` 建表。因此本 Change 需要同时维护 SQL 初始化脚本和 ORM 映射，但不引入新的迁移框架。

本 Change 是 `conversation-history-core` 的第一个叶子 Change。它只提供数据模型和存储约束；会话创建、消息追加、历史查询分别属于后续 `conversation-message-write` 和 `conversation-history-read`。

## Goals / Non-Goals

**Goals:**

- 定义 `Conversation` 与 `Message` 的最小、稳定领域表示。
- 创建 `conversation` 与 `conversation_message` 两张 PostgreSQL 表，并保证消息必须归属一个会话。
- 让数据库保护消息角色、非空内容和同一会话内的唯一顺序号。
- 提供 SQLAlchemy ORM 映射及领域记录转换边界，供后续 Repository 和测试复用。
- 通过迁移脚本和 ORM 测试验证表结构不会偏离。

**Non-Goals:**

- 不提供 HTTP API、前端页面、会话标题、会话列表或删除能力。
- 不提供创建会话、追加消息、读取消息历史的应用服务或 Repository 用例。
- 不引入 `Turn`、`ConversationEvent`、`Agent Call`、`Agent Result`、任务状态、流式状态或 Harness 追踪。
- 不保存附件、模型名称、Token 用量、Prompt、工具调用、用户主体、权限或消息元数据。
- 不修改现有单轮 `/api/v1/llm/chat` 链路。

## Decisions

### 1. 使用应用生成的 UUID 作为 Conversation 和 Message 的主键

`conversation.id` 与 `conversation_message.id` 使用 PostgreSQL `UUID` 类型；领域层在创建对象时生成 UUID，数据库不依赖扩展函数生成 ID。

选择 UUID 而不是沿用知识库的 `BIGSERIAL`，是因为 Conversation ID 会跨 HTTP、Dialogue、Agent 和未来 Harness 传播。应用生成 UUID 可在持久化前获得稳定标识，也避免把可猜测的递增主键作为长期外部引用。PostgreSQL 原生支持 `UUID` 类型，不需要额外扩展。

备选方案是 `BIGSERIAL` 加单独的外部 UUID 字段。它会增加一次不必要的双标识映射；当前不存在与旧会话表兼容的压力，因此不采用。

### 2. 使用两张直接关联的最小表，不提前引入 Turn 或事件表

表结构如下：

```text
conversation
  id: UUID 主键
  created_at: TIMESTAMPTZ
  updated_at: TIMESTAMPTZ

conversation_message
  id: UUID 主键
  conversation_id: UUID 外键 -> conversation.id
  role: TEXT
  content: TEXT
  sequence: BIGINT
  created_at: TIMESTAMPTZ
```

`conversation_message.conversation_id` 使用 `ON DELETE CASCADE`，防止未来删除会话时遗留孤儿消息。首版不暴露删除用例，该外键只定义存储完整性。

不在本 Change 增加 `Turn`、事件或 JSON 元数据表。它们需要由后续 Dialogue 与 Agent Change 的实际状态语义驱动；现在预留会把未验证的工作流概念固化进基础数据模型。

### 3. 在领域模型和数据库中同时限定最小消息不变量

消息角色限定为 `system`、`user`、`assistant`。消息内容去除首尾空白后必须非空；`sequence` 必须大于零；同一会话内 `(conversation_id, sequence)` 必须唯一。

领域层负责表达这些值的有效范围，数据库以 `CHECK`、`UNIQUE` 和外键约束作为最终保护。后续写入 Change 负责分配顺序号和处理并发冲突；本 Change 只确保错误数据不能持久化。

不预先加入 `tool`、`agent` 等角色。Agent 调用与结果将先作为后续 Conversation 事件建模；如果未来确实需要将其作为消息角色，再通过独立 Change 扩展枚举和约束。

### 4. 保持 SQL 脚本与 ORM 双轨一致，并将生产脚本作为部署入口

新增 `sql/007_conversation_model_storage.sql`，沿用现有编号和 PostgreSQL 方言。脚本创建表、约束和读取历史所需的 `(conversation_id, sequence)` 索引；它不插入业务数据。

新增 ORM 记录并注册到 `app.infrastructure.persistence.models`，使 `Base.metadata.create_all()` 能在隔离测试 schema 中创建相同表。实现时须增加测试：一组执行 SQL 脚本验证约束，另一组通过 ORM 写入和读取记录，防止两套定义长期漂移。

不引入 Alembic。现有项目的部署和 schema health 机制都以 `sql/` 脚本为基线，单独引入第二套迁移工具会扩大本 Change 的边界。

### 5. 领域对象与 ORM 记录通过专用转换边界隔离

`modules/conversation/domain` 不依赖 SQLAlchemy。基础设施层负责 `ConversationRecord`、`ConversationMessageRecord` 与领域对象之间的转换；后续 `ConversationRepository` 复用这些转换规则。

本 Change 不定义应用服务，也不让 HTTP、LLM 或 Agent 模块直接使用 ORM 记录。这样后续写入和读取 Change 可以分别添加 Port 与 Repository 方法，而不会把数据库类型泄漏到领域层。

## Risks / Trade-offs

- [SQL 脚本与 ORM 映射发生偏差] -> 增加迁移脚本约束测试和 ORM 映射测试；两者字段、默认值和约束变更必须在同一 Change 审核。
- [后续消息角色扩展需要修改约束] -> 只冻结已验证的三种文本对话角色；新角色通过新增迁移和独立 Change 演化，不使用无约束自由文本绕过模型。
- [后续并发追加产生相同 sequence] -> 数据库唯一约束会拒绝冲突；顺序号分配与重试策略留给 `conversation-message-write`，不在模型存储层伪造并发方案。
- [生产环境未执行 SQL 脚本] -> 在部署说明和 schema health 检查中加入 Conversation 表检查；在 P0.2 使用表前先验证 schema 已准备完成。
- [过早加入用户归属或留存策略] -> 当前项目没有身份认证和用户模型，本 Change 不写入虚假的 owner 字段；后续认证 Change 以独立迁移补充归属关系。

## Migration Plan

1. 新增 `sql/007_conversation_model_storage.sql`，创建 `conversation`、`conversation_message`、约束和索引。
2. 新增领域模型、ORM 记录、模型注册和转换边界。
3. 在隔离 PostgreSQL schema 中执行迁移脚本并运行 ORM 映射与约束测试。
4. 部署时先执行 `007` 脚本，再部署引用这些模型的应用代码；本 Change 本身不启用新的 HTTP 路由或后台作业。
5. 回滚时，若尚未写入业务会话数据且后续 Change 未部署，可以删除两张新表及相关索引；一旦已有生产会话数据，不执行破坏性回滚，改用前向修复迁移。

## Open Questions

- 无阻塞问题。会话归属、保留期限、标题、软删除、Turn、事件、工具结果和消息附件均由后续有明确业务行为的 Change 决定。
