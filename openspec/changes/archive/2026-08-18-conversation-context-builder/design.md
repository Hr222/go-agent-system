## Context

P0.1 至 P0.3 已提供 Conversation/Message 领域模型、事务性消息追加和按顺序分页读取。V2 架构把 Context Builder 定位为 Conversation 的应用能力：它位于已加载的历史消息与无状态 LLM 调用之间，负责把历史选择规则集中到一个可测试的边界。

当前没有 Dialogue Runtime，也没有稳定的 Provider 上下文窗口或 tokenizer 配置。若本 Change 让 Context Builder 直接读取数据库、调用 LLM 或绑定某个 tokenizer，会把 P1.2 及后续 Provider 决策提前耦合到 Conversation。

## Goals / Non-Goals

**Goals:**

- 定义模型中立的 `ModelContext` 和上下文消息值对象，保留来源消息标识、角色、内容和顺序号。
- 定义 `ContextPolicy` 与 `ContextBudget`，以“消息数量上限 + 成本上限”约束可进入模型的历史。
- 从调用方提供的单一 Conversation、有序消息窗口中选择最新的可容纳消息，并按正序返回。
- 定义可替换的消息成本计量 Port，首版提供纯 Python 的字符计量实现。
- 在 Composition Root 提供应用服务组装入口，并以单元测试固定选择、预算、顺序和失败行为。

**Non-Goals:**

- 不读取数据库、不扩展 P0.3 的分页契约，也不决定 Dialogue Runtime 如何加载最新历史窗口。
- 不构造 `ChatLlmRequest`、不调用 LLM、HTTP、Interaction Gateway 或 Agent Runtime。
- 不使用具体 Provider tokenizer；字符计量只是确定性的默认成本计量，不宣称等同于模型 Token 数。
- 不摘要、压缩、修改、拆分或持久化消息，不新增 Turn、ConversationEvent、Redis、缓存或数据库迁移。

## Decisions

### 1. 构建器接收已加载的消息窗口，而不是自行读取历史

`ConversationContextBuilder` 接收 Conversation 标识和调用方已经加载的有序 Message 序列。它不依赖 Repository 或 `ConversationReadPort`。

Dialogue Runtime 后续可以根据当前轮次、分页方向和 Provider 限制决定历史窗口；本 Change 只保证该窗口的选择结果可预测。让构建器直接使用 P0.3 的正向分页，会迫使它在没有“最新窗口”契约的情况下读取全部历史，既增加内存风险，也会把读取策略和上下文策略混在一起。

### 2. 按最新消息优先选择，但始终正序输出

构建器先校验输入属于同一 Conversation 且 `sequence` 严格递增，再以 `ContextPolicy.max_messages` 截取候选窗口的末尾。随后从最新消息向前累计成本；遇到不能容纳的较早消息后停止，不跳过它再选更早消息。最终把已选消息恢复为升序。

这种后缀选择能够优先保留当前轮次附近的内容，同时保证模型看到的因果顺序不变。静默跳过中间消息或在构建时排序会掩盖上游历史装载错误，因此不采用。

### 3. 预算通过成本计量 Port 表达

`ContextMessageCostEstimator` 负责计算一条上下文消息的非负整数成本；`ContextBudget.max_cost` 是可用成本上限。首版 `CharacterCountContextMessageCostEstimator` 按内容字符数计量，作为不依赖模型 SDK 的确定性基线。未来 Provider 或 tokenizer 适配器可以实现同一 Port，以实际 Token 规则替换它。

若最新消息本身无法放入总预算，构建器抛出明确的预算不足错误。若是更早的消息放不下，构建器保留已选的较新后缀并报告省略数量。不得切断任何消息内容，因为截断语义需要单独的策略和可追溯标记。

### 4. 契约留在 Conversation，具体组装留在 Composition Root

`ModelContext`、策略和预算是 Conversation 领域值对象；成本计量 Port 放在 Conversation ports；构建器和默认字符计量实现放在 Conversation application。`app/composition/conversation.py` 负责把默认计量实现与构建器组合。

这样 Conversation 不会反向依赖 `app.modules.llm`、SQLAlchemy 或 HTTP；未来模型相关计量适配器只能经 Port 注入。

## Risks / Trade-offs

- [调用方传入的窗口不是最新历史] → 构建器不猜测分页语义；P1.2 必须明确如何加载包含当前轮次的候选窗口。
- [字符计量与真实 Token 数存在差异] → 将其命名为成本单位而非 Token，并通过 Port 为 Provider/tokenizer 适配器预留替换点。
- [单条最新消息超过预算] → 显式抛出预算不足错误，避免模型在缺少当前输入时生成看似成功的回答。
- [输入顺序或会话归属错误] → 在构建前拒绝，避免错误上下文跨会话泄漏。

## Migration Plan

1. 部署领域契约、应用服务和 Composition Root 入口；无需数据库迁移或外部配置。
2. 先以字符成本计量运行内部调用；P1.2 接入 Dialogue Runtime 时再根据模型配置注入对应计量器和预算。
3. 回滚时移除该应用服务的调用即可；不会删除或修改任何 Conversation 数据。

## Open Questions

- P1.2 需要定义最新历史窗口的装载策略，以及当前用户消息在写入前后参与构建的时机。
- Provider 特定的 Token 预算、系统提示词和工具调用预留空间由后续 LLM/Dialogue Change 定义。
