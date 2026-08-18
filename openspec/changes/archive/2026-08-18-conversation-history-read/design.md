## Context

P0.1 建立了 Conversation/Message 的存储模型，P0.2 建立了创建会话和追加消息能力。后续 Context Builder 需要能够恢复会话元数据和有序消息，但当前还没有独立的读取端口。

本 Change 提供同步只读应用能力和 PostgreSQL 适配器。读取结果供后续 Dialogue、Context Builder 或 HTTP Change 使用；本 Change 不直接连接这些上层模块。

## Goals / Non-Goals

**Goals:**

- 返回已存在会话的 Conversation 元数据和有序 Message 历史。
- 用 `after_sequence` 游标和固定上限实现稳定分页，支持从任意消息窗口继续读取。
- 返回 `has_more` 和下一游标，避免调用方猜测是否还有历史。
- 对 UUID、页大小和游标进行应用层校验；复用 P0.2 的会话不存在错误。
- 通过 Composition Root 提供读取服务组装入口，并验证读取链路不依赖 HTTP、LLM 或 Agent。

**Non-Goals:**

- 不新增 HTTP 路由、前端页面、Context Builder、Token 预算裁剪或摘要压缩。
- 不支持按时间、角色、关键词过滤，不支持反向分页和 offset 分页。
- 不修改 Conversation/Message 表结构，不引入 Redis、缓存、事件表、Turn 或 Harness。

## Decisions

### 1. 使用按 sequence 的游标分页

读取端口接受 `conversation_id`、`limit` 和可选 `after_sequence`。查询严格按 `sequence ASC`，实际取 `limit + 1` 条以计算 `has_more`；返回的 `next_after_sequence` 是当前页最后一条消息的顺序号，仅在还有下一页时返回。

默认页大小为 50，最大页大小为 200。`after_sequence` 必须为正整数。消息只能追加、不会在本 Change 中更新或删除，因此使用顺序号游标时不会因为前面插入数据而重复或跳过。

备选方案是 offset 分页。追加消息会改变后续 offset 的位置，连续读取可能漏消息或重复消息，因此不采用。也不在本 Change 引入反向查询，最新消息窗口由后续 Context Builder 根据明确需求设计。

### 2. 返回显式的历史页结果

应用服务返回 `ConversationHistoryPage`，包含 Conversation、`tuple[Message, ...]`、`has_more` 和 `next_after_sequence`。空会话返回空元组和无下一游标，而不是返回空值或抛出“无历史”错误。

这样上层可以区分“会话不存在”和“会话存在但没有消息”，也不会依赖 SQLAlchemy Row 或 ORM 对象。领域消息仍通过 P0.1 转换边界恢复，角色和内容保持原值。

### 3. Conversation 与消息页在同一只读事务内查询

Repository 先读取 Conversation，再读取对应消息页；两次查询复用注入的 Session。只读查询不提交事务，不改变任何记录；异常时 rollback 当前 Session，向上层保留明确错误。

不使用 `FOR UPDATE`，避免历史读取阻塞 P0.2 的追加。读取过程中如果发生新的追加，游标保证后续页面仍可从上次顺序号继续读取；强一致快照不作为本 Change 的承诺。

### 4. 读取输入在应用层校验

应用服务拒绝非 UUID 会话标识、非正页大小、超过 200 的页大小和非法游标。不存在的会话由 Repository 抛出 `ConversationNotFoundError`；存在但没有消息的会话返回空页。

不在读取层吞掉数据库异常，也不把错误转换成“空历史”，避免把存储故障误报为正常空结果。

### 5. 具体 Repository 只在 Composition Root 组装

新增 `build_conversation_history_read_repository` 和 `build_conversation_history_read_service`，接收外部注入的 SQLAlchemy Session。Conversation 应用模块和未来 HTTP 层只依赖读取 Port 与结果契约。

## Risks / Trade-offs

- [单页最多返回 200 条消息，超出部分需要多次读取] → 返回明确的下一游标；后续 Context Builder 再根据模型预算决定读取窗口。
- [追加与读取并发时不是完整快照] → 只承诺按游标的有序读取，不承诺跨页强一致；需要快照时由后续 Change 定义版本或事件语义。
- [数据库读取异常被误当成空历史] → Repository 只对“会话不存在”做领域错误映射，其他异常原样抛出并 rollback。
- [ORM 映射与领域页结果不一致] → 复用 P0.1 转换函数，并用数据库集成测试核对 UUID、角色、内容和顺序。

## Migration Plan

1. 确认 P0.1 的 Conversation 表和 P0.2 的写入代码已部署。
2. 部署读取 Port、应用服务、PostgreSQL Repository 和 Composition 组装；不执行数据迁移。
3. 运行读取、分页、空历史、缺失会话、架构边界及 V1 回归测试。
4. 回滚时停止读取服务并回滚应用代码，不删除已有会话数据和表结构。

## Open Questions

- 无阻塞问题。HTTP 查询参数、最新窗口读取、Context Policy、Token 预算和强一致快照由后续 Change 定义。
