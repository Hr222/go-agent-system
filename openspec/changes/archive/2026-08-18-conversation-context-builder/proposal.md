## Why

P0.1 至 P0.3 已经能够持久化、追加和分页读取 Conversation 历史，但还没有把有序历史转换为可供后续对话模型使用的稳定输入。若由 Dialogue Runtime 或 LLM 适配器各自裁剪消息，历史选择规则、预算边界和消息顺序会分散，无法稳定演化为多轮对话。

## What Changes

- 在 Conversation 模块新增模型中立的 `ModelContext`、上下文消息、`ContextPolicy` 和 `ContextBudget` 契约。
- 新增纯应用服务：接收上层已加载的同一会话有序消息窗口，按最近消息优先选择，并按原始顺序输出模型上下文。
- 通过可替换的消息成本计量 Port 执行预算裁剪；首版提供确定性的字符计量实现，为后续按 Provider 或 tokenizer 计量保留插口。
- 明确单条最新消息本身超出预算时的显式失败，禁止静默截断、重排或跳过较新的消息。
- 新增 Composition Root 组装入口及单元、架构边界测试；不新增 HTTP 路由、数据库表、LLM 调用或 Agent 调用。

## Capabilities

### New Capabilities

- `conversation-context-builder`：从已加载的 Conversation 消息窗口选择历史并构造受策略与预算约束的模型中立上下文。

### Modified Capabilities

- 无。

## Impact

- 影响 `app/modules/conversation/domain`、`application` 和 `ports`，新增上下文值对象、预算计量 Port 和构建服务。
- 影响 `app/composition/conversation.py`，增加上下文构建服务的组装入口。
- 不修改 PostgreSQL Schema、Repository、现有 HTTP 契约、前端、`app/modules/llm`、Interaction Gateway 或 Agent Runtime。
- 不引入 Redis、缓存、摘要压缩、Token SDK、Task Management、Turn、ConversationEvent 或 Harness。
