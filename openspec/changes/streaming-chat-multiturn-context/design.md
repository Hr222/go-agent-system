## Context

当前普通流式 Conversation Runtime 已负责主体范围的会话创建/解析、本轮 user Message 写入、上游流式调用和成功后的 assistant Message 写入，但它仍使用没有历史消息的 `ChatLlmRequest`。Conversation 模块已经提供历史分页读取服务、模型中立的 `ModelContext` 和按最近连续消息及成本预算选择窗口的 Context Builder；LLM Port 也已经支持带角色的 `history_messages`。

本 Change 的目标是把这些已有能力接到普通流式入口，形成最小可用的同一会话多轮对话。PostgreSQL 继续作为消息事实源，Context Builder 继续属于 Conversation 应用能力，LLM 适配器只消费本轮请求上下文。

## Goals / Non-Goals

**Goals:**

- 普通流式请求在写入本轮 user Message 后读取当前 Conversation 的有序历史。
- 使用现有 Context Builder 选择最多 20 条、成本不超过 12,000 的最近连续消息窗口。
- 将窗口中的历史角色和顺序映射到 `ChatLlmRequest.history_messages`，当前 user Message 从上下文末尾剔除后作为 `user_prompt` 发送一次。
- 保持首轮创建、访问控制、SSE 事件、流式关闭、assistant 持久化和失败事实语义。
- 让历史读取或上下文预算错误在流式开始前或既有受控错误边界内安全失败，不暴露数据库或 Provider 细节。

**Non-Goals:**

- 不新增摘要、压缩、摘要检查点或异步 Compaction Worker。
- 不修改 PostgreSQL Schema、消息领域模型、HTTP 请求/响应结构或前端代码。
- 不引入精确 Tokenizer、Redis、跨会话长期记忆、用户画像或 Agent 专用上下文规则。
- 不改变 Agent 调用确认和结果续写的既有上下文链路。

## Decisions

### 1. 在写入 user Message 后读取历史，再构建上下文

本轮 user Message 必须先持久化，才能获得真实 sequence 并让历史读取看到完整的当前轮次。随后读取当前 Conversation 的分页历史并交给 Context Builder。这样当前消息可被校验为上下文最后一条，再从 `history_messages` 中移除，避免同时出现在历史和 `user_prompt` 中。

替代方案是写入前读取历史并把当前输入临时拼入窗口；该方案无法复用消息 sequence 和统一预算校验，也更容易造成重复输入，因此不采用。

### 2. 由 Dialogue Runtime 负责历史分页，Context Builder 负责选择

Streaming Runtime 复用 `ConversationHistoryReadService`，按正向 `after_sequence` 游标读取至最后一页，然后把有序消息窗口交给 Context Builder。Builder 不直接依赖 Repository，也不猜测分页状态，继续保持 Conversation 与基础设施边界。

替代方案是让 Builder 自行查库或新增“倒序最新窗口”仓储接口；这会扩大本 Change 的持久化范围并混合读取和预算策略，留给后续窗口优化 Change。

### 3. 保留连续后缀和现有基线预算

第一期直接使用既有 `ContextPolicy(max_messages=20)` 和 `ContextBudget(max_cost=12_000)`。Builder 从最新消息向前选择连续后缀，输出恢复为升序。若当前最新 user Message 单独超预算，返回明确预算不足错误，不截断当前输入，也不伪造 assistant Message。

### 4. 复用模型中立角色映射

`MessageRole` 映射为 `ChatLlmMessageRole`，历史 system/user/assistant 消息保持原角色。System prompt 继续由 Runtime 作为请求级系统提示发送；Conversation 中若存在 system Message，则作为历史消息保留，不改写为 user。

### 5. 失败事实保持不变

历史读取、上下文构建、Provider 流、客户端取消或 assistant 写入失败时，已成功写入的 user Message 保留；不得写入空或部分 assistant Message。既有 Interaction 层错误码和 SSE 事件外形保持不变，内部异常只映射为现有受控失败语义。

## Risks / Trade-offs

- [正向分页会读取较多历史] -> 第一版沿用最多 200 条一页和 Builder 的 20 条窗口；后续 `turn-aware-context-window` 再优化为按轮次或倒序窗口读取。
- [字符成本不等于 Provider Token] -> 本 Change 明确使用现有字符成本基线；精确 Token 预算另立 Change。
- [历史读取或上下文失败发生在 user 写入后] -> 保留 user 事实且不写 assistant，沿用已有失败语义，避免虚构完成。
- [并发请求同时追加同一会话] -> 继续依赖现有 sequence 唯一约束和写入事务；本 Change 不承诺消息级幂等或并发轮次排序。
- [历史中已有不完整的失败轮次] -> Context Builder 按实际持久化 Message 选择；失败轮次只有 user Message 时仍作为用户事实参与上下文。

## Migration Plan

1. 扩展 Streaming Runtime 的应用层依赖，注入历史读取服务和 Context Builder。
2. 部署后新请求自动按当前会话历史构建多轮上下文；已有消息无需迁移。
3. 若需回滚，只移除 Runtime 对历史上下文的调用并恢复空 `history_messages`；不会删除任何 Conversation 数据。

## Open Questions

- 历史窗口是否必须以完整 user/assistant 轮次为单位，将在 `turn-aware-context-window` Change 中确定。
- 摘要检查点、压缩触发阈值和异步生成由后续 Change 定义。
