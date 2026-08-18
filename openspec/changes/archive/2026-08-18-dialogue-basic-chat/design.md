## Context

P0 已提供 Conversation 的事务性追加和按顺序分页读取，P1.1 已能从调用方提供的消息窗口选择受预算限制的 `ModelContext`。现有 LLM `ChatLlmPort` 只承载系统提示和当前用户提示，V1 HTTP 接口也始终是无状态单轮调用。因此，项目尚不能执行“写入用户输入、恢复历史、调用模型、写入回答”的完整对话轮次。

本 Change 创建独立的 `Dialogue Runtime` 应用能力。它可以依赖 Conversation 和 LLM 两个同级模块，但不拥有它们的持久化模型或 Provider 适配器。Interaction Gateway、Agent Runtime、Turn/Event、HTTP API 和流式协议尚未具备所需契约，均不进入本轮。

## Goals / Non-Goals

**Goals:**

- 新增同步基础对话运行时，输入已有 Conversation 标识和用户文本，返回持久化的用户消息、助手消息、模型元数据与所用 `ModelContext`。
- 使用现有 Conversation 写入、分页读取和 Context Builder；在 P0.3 只有正向分页时仍保证选择到最新消息窗口。
- 使 `ChatLlmPort` 支持可选、顺序明确的 system/user/assistant 历史消息，且 V1 单轮调用保持空历史。
- 在 Composition Root 组装 Dialogue Runtime，保持 Dialogue、Conversation、LLM 和具体适配器的依赖方向清晰。
- 固定 LLM、上下文构建和持久化失败时的消息保留语义。

**Non-Goals:**

- 不新增或修改 HTTP 路由、前端、SSE、请求 Schema 或 `/api/v1/llm/chat` 行为。
- 不调用 Gateway、能力目录、Agent Runtime、Tender Agent、RAG 或知识库。
- 不新增 Turn、ConversationEvent、幂等键、重试、取消、恢复执行、摘要压缩或并行消息写入策略。
- 不新增数据库表、迁移、Redis、缓存或 Provider 专属 tokenizer。

## Decisions

### 1. Dialogue Runtime 按可恢复事实顺序持久化消息

执行顺序为：校验并标准化用户文本 -> 追加 user Message -> 分页装载历史 -> 构建 `ModelContext` -> 调用 LLM -> 校验回答 -> 追加 assistant Message -> 返回结果。

用户消息一旦成功追加便不因后续外部 LLM 失败而回滚；这条消息是已接收的用户事实。只有获得非空模型回答后才追加 assistant Message，因此失败路径不会伪造回答。跨网络调用与数据库事务无法原子提交，本 Change 也不假装提供 exactly-once 语义；重试和恢复由后续 Turn/Event Change 解决。

### 2. 用有界内存扫描正向历史以获得最新窗口

P0.3 只支持按 `after_sequence` 向前分页，而 Context Builder 必须优先保留最新消息。Dialogue Runtime 逐页读取到末尾，但只在内存中保留 `ContextPolicy.max_messages` 条最近消息，再把该窗口交给 Context Builder 执行成本预算。

这保证当前刚追加的用户消息不会因前面历史过长而消失，内存复杂度受策略约束。它的代价是长会话读取成本为 O(n) 页；不在本 Change 改动 P0.3 读取契约，后续可通过独立 Change 增加反向窗口查询。

### 3. LLM 请求新增可选历史消息而不重写 V1 入口

LLM 模块定义独立的 `ChatLlmMessage`（system/user/assistant）并在 `ChatLlmRequest` 中新增默认空的 `history_messages`。Dialogue Runtime 把 `ModelContext` 中当前用户消息之前的记录映射为该列表，并仍将当前用户文本放入 `user_prompt`。Provider 适配器固定输出顺序为：运行时系统提示 -> 历史消息 -> 当前用户消息。

不把 Conversation 的 `Message` 直接暴露给 LLM 模块，避免 LLM 反向依赖 Conversation。旧 `ChatApplication` 不设置历史字段，Provider 收到的两条消息顺序保持不变。

### 4. 运行时只调用抽象服务，由 Composition Root 绑定基础设施

Dialogue Runtime 构造时接收 `ConversationWriteService`、`ConversationHistoryReadService`、`ConversationContextBuilder` 和 `ChatLlmPort`。`app/composition/dialogue.py` 使用同一个外部注入的 SQLAlchemy Session 组装 Conversation 服务，并注入现有 Chat LLM 适配器。

Dialogue 的应用层可以依赖 Conversation 和 LLM 的公开契约，但不得导入 SQLAlchemy、HTTP、LangChain 或具体 Repository/Provider 类。

## Risks / Trade-offs

- [历史较长时扫描所有前向页带来额外读取] → 只保留有界的最近窗口，并在后续 Change 单独设计反向读取或快照能力。
- [LLM 成功但助手消息写入失败] → 调用失败显式向上返回；本轮不重新调用模型，避免无幂等保护时制造重复回答。
- [用户消息写入后 LLM/上下文失败] → 保留用户消息且不写助手消息；未来 Turn/Event 能够基于该事实表达失败和重试。
- [角色提示在不同 Provider 上语义存在差异] → 所有 OpenAI-compatible 适配器使用同一顺序与角色映射，并用适配器测试固定。

## Migration Plan

1. 部署 LLM 可选历史消息契约及 Provider 映射；无历史的 V1 调用保持原请求形态。
2. 部署 Dialogue Runtime 与 Composition Root；因没有 HTTP 入口，不影响现有流量。
3. 后续 Dialogue API Change 显式装配并验收该运行时后，再考虑 V1 入口退场。
4. 回滚时停止使用新的运行时即可；已写入的 Conversation 消息保持可读，不删除数据。

## Open Questions

- 反向读取、快照和长会话读取性能由独立 Conversation Change 处理。
- Turn、失败事件、幂等请求标识和用户可见重试语义由后续 Dialogue Change 定义。
- Gateway 与 Agent Call 接入后，模型上下文需要加入授权范围和 Agent 结果，但不改变基础文本轮次的持久化顺序。
