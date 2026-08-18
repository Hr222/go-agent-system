## Context

仓库已有 `ExplicitCapabilityConfirmation`、`PendingProposalStorePort` 和进程内短 TTL 存储。它们能够依据目录重新校验识别结果、生成提议、处理确认或取消，并通过主体绑定和原子消费跨 HTTP 请求保存短期状态。旧 `IntentInteractionGateway` 为既有接口把确认结果继续交给 Dispatcher，但这一执行组合不属于 P2.3 的确认核心。

P2.3 的职责是把“用户同意”变成受控、可一次消费的确认状态，而不是把它视为最终执行授权。结构化 Agent Call、调用策略校验和分发将由 P2.4 至 P2.6 接续。

## Goals / Non-Goals

**Goals:**

- 仅为目录策略为 `always` 或按 `always` 处理的 `conditional` 条目创建待确认提议。
- 让待确认提议在服务端以深拷贝快照保存，按主体绑定、TTL 过期和一次消费处理。
- 保持确认服务与提议存储不依赖具体 Agent、LLM Provider、RAG、Conversation、Task Management 或 Dispatcher。

**Non-Goals:**

- 不创建新的 HTTP 接口或前端确认控件，不修改现有旧交互路由。
- 不将确认结果写入 Conversation，不持久化 PostgreSQL，不引入 Redis。
- 不定义结构化 Agent Call、不复核执行策略、不执行目标能力。

## Decisions

### 1. 由确认核心再次执行确认策略门控

确认服务重新读取目录并校验输入后，只有 `always` 与 `conditional` 能力可以生成待确认提议。`never` 是服务器受控直连路径的策略，不得通过确认核心变形成待确认对象。

替代方案是完全依赖上游 Gateway 先分流。这样直接调用确认服务时会绕过策略门控，因此不采用。

### 2. 提议存储采用服务端快照和原子消费

保存时深拷贝提议，取回时再次返回深拷贝，避免调用方持有的 Pydantic 对象或 `inputs` 字典在保存后影响服务端记录。消费操作仍在同一把锁内检查过期、检查主体、删除记录并返回提议；主体不匹配不得消耗提议。

替代方案是依赖调用方不修改对象。该方案无法为确认状态提供可靠的边界，因此不采用。

### 3. 确认结果不是执行行为

确认服务最多返回已确认的受控提议数据，不能导入或调用执行器。旧 Gateway 的兼容分发组合维持原状，不被作为 P2.3 的新能力；P2.6 将建立新的受控分发边界。

## Risks / Trade-offs

- [进程重启丢失待确认提议] -> 首版 TTL 状态明确为短期进程内状态，客户端收到不可用结果后重新发起请求；持久恢复留给未来独立 change。
- [深拷贝增加很小的内存和 CPU 成本] -> 提议仅包含有限输入，代价远小于避免状态被修改的收益。
- [`conditional` 尚无独立规则] -> 沿用目录既定语义，按 `always` 处理。

## Migration Plan

无需数据迁移或 API 迁移。部署后新创建的提议自动使用快照；旧进程内提议不跨进程保留。回滚只恢复内存存储实现，不影响目录或 Conversation 数据。

## Open Questions

无。长期确认恢复和 Conversation Event 记录将在实际引入事件模型的独立 change 中讨论。
