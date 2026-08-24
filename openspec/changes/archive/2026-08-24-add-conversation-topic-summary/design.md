## Context

当前 Conversation 已支持主体范围的创建、列表、历史读取和流式消息持久化，但列表只能使用创建/更新时间显示“会话 + 日期”。Conversation 领域记录还没有可编辑的话题概括字段。

本 Change 同时影响持久化、Conversation 应用能力、HTTP 适配器和 Chat 侧栏。实现必须保持 owner-scoped 访问边界，不能把话题概括当作模型上下文或完整历史摘要。

## Goals / Non-Goals

**Goals:**

- 保存每个 Conversation 的可编辑 `topic_summary`。
- 在没有人工标题的新会话首轮消息完成后生成简短概括。
- 生成失败时不影响消息持久化和流式回答，并提供稳定回退文本。
- 让列表返回话题概括，并允许当前主体修改或清除它。

**Non-Goals:**

- 不生成完整历史摘要，不改变模型上下文窗口。
- 不引入异步任务队列、独立标题模型或新的 LLM Provider。
- 不实现正文搜索、批量重命名、删除和真实用户认证。

## Decisions

### 1. 使用可空的 `topic_summary` 字段

Conversation 增加可空文本字段，最大长度由应用层和数据库约束共同限制。历史会话迁移后保持 `NULL`，前端继续使用日期回退，避免猜测历史主题。

### 2. 首版使用本地规则型概括器

首轮用户消息成功写入后，应用层调用 Conversation Topic Summary Generator：规范化空白、提取首句并截断到固定长度。这样不增加一次 LLM 调用的延迟和费用，也不让 Provider 不可用阻塞普通 Chat。生成器通过独立端口注入，未来可替换为 LLM 实现而不改变 HTTP 或 Domain 契约。

如果生成器抛错或结果为空，应用层使用同一条用户消息的安全截断值作为回退；如果回退也不可用，则保持 `NULL`。手动标题一旦存在，后续消息不得自动覆盖。

### 3. 修改和清除使用 owner-scoped HTTP 契约

新增 `PATCH /api/v1/conversations/{conversation_id}/topic-summary`。请求只允许 `topic_summary` 字段，支持非空标题和显式 `null` 清除；路由先通过 Conversation Access 校验主体，再调用应用服务更新。响应返回最小 Conversation 摘要，不返回消息或事件。

### 4. 复用列表摘要契约

`GET /api/v1/conversations` 的每项摘要增加可空 `topic_summary`。排序、游标和主体过滤保持现有语义，前端在缺少标题时回退为日期。

### 5. 数据迁移与失败边界

新增幂等 SQL migration，为现有记录增加可空字段和长度约束，不回填历史主题。更新标题使用单条事务；自动概括属于 best-effort，失败只记录可观测日志，不回滚已经成功写入的消息或流式回答。

## Risks / Trade-offs

- [规则型概括可能不如 LLM 自然] -> 先保证低延迟和稳定闭环，保留 Generator Port，未来另立 Change 引入模型生成。
- [标题生成和消息写入之间出现短暂不一致] -> 话题概括更新独立提交；列表缺少标题时始终提供日期回退。
- [用户清除标题后再次产生首轮判断歧义] -> 只有会话从未有过标题且首轮消息完成时自动生成；手动清除后保持空值，不在后续消息中自动覆盖。
- [历史数据库未执行 migration] -> 启动检查和迁移验证补充 `topic_summary` 字段检查；migration 保持可重复执行。

## Migration Plan

1. 备份 `conversation` 表。
2. 执行新增 `topic_summary` 的幂等 migration，历史记录保持 `NULL`。
3. 发布后端 Domain、Repository、HTTP 和前端代码。
4. 验证列表、自动概括、手动修改/清除和 owner 越权拒绝。

回滚时先停止新标题写入，再回滚应用代码；字段保留不会影响旧代码读取。只有确认不再需要标题数据时，才单独执行删除字段的破坏性 migration。

## Open Questions

- 无。首版标题生成策略固定为本地规则型概括；LLM 生成留给后续独立 Change。
