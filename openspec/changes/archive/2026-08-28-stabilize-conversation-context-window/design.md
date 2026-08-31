## Context

归档的 `streaming-chat-multiturn-context` 已把普通流式 Chat 接到 Conversation 历史和 Context Builder，但当前运行时仍从 `after_sequence = None` 开始正向分页，直到读完整个会话，再让 Builder 从内存中选择最近消息。实现中的历史列表会持续增长，长会话的数据库读取量随历史总长度增长；这些读取和消息写入还使用同步 SQLAlchemy `Session`，直接发生在异步流式请求路径。

当前 user Message 已先提交并获得真实 `sequence`。已归档的 Conversation 轮次串行化 Change 已在 Dialogue Application 中提供进程共享的 `ConversationTurnCoordinator`：普通流式 Runtime 在写入 user 前取得租约，并持有至 Provider 流和 assistant 终态收口。同一 Conversation 的普通 Chat 不会在当前轮次结束前写入后续 user 或调用 Provider；不同 Conversation 仍可并行。

因此，本 Change 不再把“请求级快照”作为解决同会话并发的主机制。`sequence` 只作为租约内数据库读取的包含边界，用于让上下文读取契约自洽，并防止任何不受该租约覆盖的后续写入污染本轮。`_build_llm_request` 仍要求上下文最后一条是当前 user，但这个条件由“租约 + sequence 截止”共同保证。

本 Change 需要在不改变 Conversation/Message 事实模型、HTTP/SSE 外形和既有预算契约的前提下，让每轮基于明确的有界历史快照工作。PostgreSQL 现有 `(conversation_id, sequence)` 唯一约束可以为按会话顺序截取最近消息提供索引基础。

## Goals / Non-Goals

**Goals:**

- 为上下文构建提供按 `through_sequence` 截止的最近消息窗口读取能力，读取量受 `ContextPolicy.max_messages` 限制。
- 让普通流式 Chat 在既有会话轮次租约内使用本轮 user Message 的 sequence 建立数据库读取边界，排除边界之外的消息。
- 保持既有会话轮次租约的取得时机、覆盖范围、释放和引用回收语义，不引入第二套协调机制。
- 复用现有 `ConversationContextBuilder`、`ContextBudget` 和成本计量器，在有界窗口内完成消息选择和预算校验。
- 让流式 Dialogue 对同步 Conversation 持久化访问使用明确的异步执行边界，不跨线程共享请求级 SQLAlchemy Session，也不在 Provider 流期间占用数据库连接。
- 保持 user 先落库、完整非空 assistant 成功后落库、取消/上游失败不写 assistant 的事实语义。

**Non-Goals:**

- 不新增会话锁、FIFO 排队、长事务或分布式协调；同一 Conversation 继续由已有 `ConversationTurnCoordinator` 串行，sequence 边界不替代租约。
- 不引入 Turn、ConversationEvent、幂等键、摘要检查点、摘要压缩、完整 user/assistant 轮次选择或跨会话记忆。
- 不改变 Conversation 的公开正向游标分页 HTTP 契约；上下文最近窗口使用内部专用读取契约。
- 不引入 Provider 专属 tokenizer，不把当前字符成本单位改名或声称为精确 Provider token。
- 不修改 Agent invocation、Agent continuation、Interaction 确认分支或前端状态管理。

## Decisions

### 1. 增加上下文专用的最近消息读取契约

在 Conversation 的 Application/Ports 边界增加只读的最近窗口能力，输入为 `conversation_id`、`through_sequence` 和消息数量上限，返回 `sequence <= through_sequence` 的消息。基础设施适配器执行：

1. 按 `conversation_id` 和 `sequence <= through_sequence` 过滤；
2. 按 `sequence DESC` 查询并限制为请求上限；
3. 在适配器内恢复为 `sequence ASC` 后返回。

上限直接取当前流式上下文策略的 `max_messages`，因为 Context Builder 不会选择更多消息。这样既不会因预算不足而需要读取整段历史，也不会把更早消息加载到应用层。现有面向浏览器历史恢复的正向分页仍保留原契约，不把“最近窗口”伪装成普通分页。

选择专用读取契约而不是让现有分页增加方向参数，是为了避免破坏历史恢复游标语义，并让“用于模型上下文的有界窗口”与“用于用户查看的完整历史”保持清晰边界。

### 2. 复用既有轮次租约，并以 user sequence 作为读取边界

普通流式 Runtime 先按既有架构解析或创建 Conversation，再取得共享的 Conversation 轮次租约；只有持有租约后才写入 user。user Message 提交成功后保存其 `sequence`，随后只读取 `sequence <= current_user.sequence` 的最近窗口。正常普通 Chat 的同会话后续请求此时仍在租约外等待，不会提前追加消息；sequence 边界同时为读取 Port 提供明确、可测试的数据库截止条件。

这里的职责划分是：

- 会话租约负责同一 Conversation 的轮次互斥和事实写入顺序；
- sequence 边界负责一次最近消息读取不能越过本轮 user；
- 最近窗口负责限制候选读取量；Context Builder 负责预算裁剪。

sequence 边界不承诺或改变租约等待顺序，也不新增模型完成顺序语义。一个轮次释放租约后，后续轮次按已有协调器规则开始，并读取此前已完整持久化的事实。

### 3. 预算仍由 Context Builder 统一执行

Runtime 将有界窗口交给现有 Context Builder，并继续传入现有 `ContextPolicy` 和 `ContextBudget`。Builder 负责连续后缀、字符成本、最新消息超预算和正序输出；最近窗口读取器不重新实现预算逻辑，也不按字符串自行截断内容。

因此，读取上限是性能边界，Context Budget 是模型输入的成本边界，两者职责不同但顺序固定：先按 sequence 获取最多候选消息，再由 Builder 按现有策略裁剪。当前默认 `max_messages = 20`、`max_cost = 12_000` 不变。

### 4. 为同步持久化建立异步执行边界

现有 Conversation Repository 继续使用同步 SQLAlchemy，以保持既有应用服务和其他同步调用方稳定。流式 Dialogue 通过新的异步持久化门面调用创建/解析、user 写入、最近窗口读取和 assistant 写入；门面在 worker 中执行同步应用服务，并由基础设施使用 `SessionLocal` 工厂为每个短操作创建、提交或回滚并关闭独立 Session。

请求级 Session 不跨线程传递，Provider 流期间不持有数据库 Session。上下文构建本身只处理最多策略上限的纯领域消息，可在异步任务中直接执行；assistant 写入在完整回答形成后再次通过异步门面执行。这样不需要把整个 Conversation 模块一次性迁移到 AsyncSession，也不会用 `asyncio.to_thread` 共享非线程安全的 SQLAlchemy Session。

### 5. 保持失败和安全边界

Access 校验仍在写入前执行，读取器只接受已经准入的 Conversation 标识。读取结果必须再次校验会话归属、sequence 升序和当前 user 的来源标识；任何边界异常都在模型调用前失败。历史读取、预算、Provider、取消和 assistant 写入失败时，已提交的 user 保留，不写入空或部分 assistant。

本 Change 不新增公开错误码或 SSE 字段。现有 Interaction 层继续负责把内部异常映射为浏览器安全事件；如果后续要把预算错误与输入错误拆分，另立协议 Change。

## Risks / Trade-offs

- [读取边界与租约覆盖范围未来可能被新写入路径绕开] → 普通 Chat 和已确认 Agent 继续统一经既有租约进入轮次；最近窗口 Port 强制使用 sequence 截止，架构测试检查不得重新引入请求级同步 Session。
- [每轮仍可能读取最多 20 条较长消息] → 读取量和内存量由策略上限约束；Context Budget 继续拒绝超预算最新消息，不做静默截断。
- [worker session 增加线程切换和连接创建开销] → 每个操作只做短事务并及时关闭；用 PostgreSQL 集成测试和连接释放检查验证，避免持有连接跨模型流。
- [查询计划未使用现有唯一约束的索引] → 增加 PostgreSQL `EXPLAIN`/执行计划验收；只有确认必要时才新增最小复合索引迁移，不为预防性优化扩大 Schema。
- [user 写入后到快照读取之间会有并发追加] → `through_sequence` 明确排除更晚消息；当前 user 仍是自己的快照末尾，避免旧的“最后一条不是当前 user”失败。

## Migration Plan

1. 增加 Conversation 最近窗口 Port、应用服务和 PostgreSQL 适配器，实现倒序限量查询及正序恢复；保留现有正向历史分页。
2. 增加流式 Dialogue 的异步持久化门面，在 Composition Root 以 Session 工厂组装，并替换普通流式 Runtime 的完整历史扫描。
3. 让 Runtime 以本轮 user sequence 构建快照，继续调用既有 Context Builder 和 LLM 请求映射。
4. 先运行 Conversation/Dialogue 单元测试，再运行 PostgreSQL 查询、并发、流式取消和全量回归；验证 `git diff --check` 与 OpenSpec 严格校验。
5. 回滚时可恢复 Runtime 对旧历史读取服务的调用并保留既有租约；本 Change 不改变已有数据、不需要数据迁移。保留的最近窗口 Port 不会影响历史恢复接口。

## Open Questions

- 完整 user/assistant 轮次窗口、失败轮次是否应被跳过，以及并发请求是否需要排队，由后续 Turn/ConversationEvent Change 决定。
- Provider 精确 token 计量和系统提示/工具调用预留空间继续由后续模型上下文 Change 决定；本 Change 只复用现有成本预算。
