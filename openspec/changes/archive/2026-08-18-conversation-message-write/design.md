## Context

P0.1 已完成 `conversation` 与 `conversation_message` 的领域模型、PostgreSQL 表、ORM 映射和转换边界，但没有写入用例。P0.2 需要为后续历史读取和 Dialogue Runtime 提供稳定的创建、追加消息能力，同时保证调用方不直接操作 SQLAlchemy。

本 Change 只处理同步、短事务的 Conversation 写入。现有 V1 单轮 Chat、HTTP 层、前端、LLM、Agent 和 Task Management 均不参与这条链路。

## Goals / Non-Goals

**Goals:**

- 提供创建 Conversation 和向已有 Conversation 追加 Message 的应用服务。
- 通过 Conversation 写入 Port 隔离应用层与 PostgreSQL Repository。
- 由服务端分配消息顺序号，首条消息从 1 开始，并在同一会话并发追加时保持连续且唯一。
- 追加成功后更新 Conversation 的 `updated_at`，失败时回滚本次写入。
- 在 Composition Root 提供具体 Repository 的组装入口，并用领域、应用、PostgreSQL 集成和架构测试验证边界。

**Non-Goals:**

- 不提供历史读取、会话列表、删除接口、HTTP 路由或前端页面。
- 不引入 Redis、缓存、异步队列、幂等请求键、Turn、ConversationEvent、Task Management 或 Harness。
- 不改变 P0.1 的表结构和消息角色集合，不调用 LLM、Interaction Gateway 或 Agent Runtime。

## Decisions

### 1. 应用层通过写入 Port 暴露两个最小用例

Conversation 应用服务只暴露 `create_conversation()` 和 `append_message(conversation_id, role, content)`。服务接收领域类型或基础值并返回领域对象；不接收 HTTP Schema，也不返回 ORM 记录。

端口由 `modules/conversation/ports` 定义，基础设施 Repository 实现该端口。这样后续 HTTP、Dialogue Runtime 或测试替身可以复用同一写入契约，不需要依赖数据库会话。

备选方案是让应用服务直接依赖现有 SQLAlchemy Session。该做法会把事务、ORM 和数据库异常泄漏到 Conversation 模块，违反现有依赖方向，因此不采用。

### 2. 在 Repository 内完成一次追加的事务

追加流程在同一个数据库事务中完成：先对目标 Conversation 行执行 `SELECT ... FOR UPDATE`，再读取该会话当前最大 `sequence`，生成下一个序号，写入 Message，并更新 Conversation 的 `updated_at`，最后提交。

会话行锁使同一会话的并发追加串行化；不同会话之间不互相阻塞。数据库现有唯一约束仍是最终保护，若出现数据库冲突，Repository 必须回滚并向上抛出明确错误。

备选方案是仅使用 `MAX(sequence) + 1` 而不加锁。并发请求会计算出相同序号并依赖冲突重试，行为不稳定且会把并发策略推给上层，因此不采用。也不使用全局序列，因为消息顺序需要按会话从 1 开始。

### 3. 领域校验先行，数据库约束兜底

应用服务先使用 `MessageRole` 和消息内容的领域规则完成输入校验；Repository 获得会话锁并分配顺序号后，再构造完整的 `Message` 领域对象。Repository 仍依赖 P0.1 的数据库约束保护外键和唯一性，不能通过绕过领域模型写入无效记录。

不存在的 Conversation 映射为明确的 `ConversationNotFoundError`；领域输入无效直接返回校验错误。事务失败必须先 rollback，再将错误交给上层，不吞掉原始原因。

### 4. 不在本 Change 引入请求幂等语义

创建会话和追加消息使用应用生成的 UUID。当前端或上层在提交结果未知时重试，可能产生新的会话或重复消息；本 Change 不增加 `idempotency_key` 或客户端消息 ID。需要幂等重试时由后续 Dialogue/HTTP Change 先定义契约，再扩展数据模型。

### 5. 具体 Repository 只在 Composition Root 组装

新增 `app/composition/conversation.py`，根据注入的 SQLAlchemy `Session` 返回 Conversation 写入 Repository 和应用服务。没有 HTTP 使用方时不把该服务强行挂到现有路由或全局容器，后续 Dialogue Change 再接入正式入口。

## Risks / Trade-offs

- [同一会话的高并发写入会在行锁处排队] → 只锁目标 Conversation 行，不锁全表；后续若需要流式或高吞吐写入再单独评估事件/队列模型。
- [提交结果未知时重试可能重复追加] → 当前明确不承诺幂等；后续在 HTTP 或 Dialogue Change 中引入请求键前，不能对外宣称自动去重。
- [ORM 与领域模型转换发生偏差] → 复用 P0.1 映射函数，并增加应用结果与数据库恢复的集成测试。
- [数据库表尚未执行 P0.1 脚本] → Repository 保持原始数据库错误；部署检查和 schema health 更新留给独立迁移/部署 Change。
- [更新 `updated_at` 与消息写入不一致] → 两者位于同一事务；任一步失败都 rollback，成功测试同时检查消息和会话更新时间。

## Migration Plan

1. 部署前确认 P0.1 的 `sql/007_conversation_model_storage.sql` 已执行。
2. 部署应用代码和 Conversation 写入 Port、Repository、应用服务及 Composition 组装。
3. 运行领域、应用、PostgreSQL 并发和架构边界测试；本 Change 不需要新增 SQL 脚本或数据回填。
4. 回滚时先停止使用写入服务，再回滚应用代码；不删除 P0.1 表，避免已创建的会话数据丢失。

## Open Questions

- 无阻塞问题。HTTP 错误码、客户端幂等键、历史读取分页和上下文截断由后续 Change 定义。
