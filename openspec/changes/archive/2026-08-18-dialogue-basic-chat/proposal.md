## Why

Conversation 已能够保存、读取和裁剪历史，Context Builder 也已能生成模型中立上下文；但系统仍没有把这些能力与无状态 LLM 调用编排成一个完整的多轮对话。当前 V1 `/api/v1/llm/chat` 不能作为该运行时的替代品，因为它不持久化消息，也不接收历史。

## What Changes

- 新增 `Dialogue Runtime` 的同步基础对话用例：持久化用户消息、加载有序历史、构建 `ModelContext`、调用 LLM、持久化助手消息并返回本轮结果。
- 扩展内部 `ChatLlmRequest`，使其可选携带有角色和顺序的历史消息；现有单轮调用保持空历史的既有行为。
- 更新 OpenAI-compatible Chat 适配器，把系统提示、历史 system/user/assistant 消息和当前用户消息按角色顺序交给 Provider。
- 明确失败边界：LLM、上下文构建或助手消息写入失败时，不伪造助手消息；已经成功持久化的用户消息不回滚。
- 新增 Dialogue Composition Root、单元/数据库集成/Provider 映射和架构边界测试；不新增 HTTP 路由、前端、Gateway、Agent 或流式对话。

## Capabilities

### New Capabilities

- `dialogue-basic-chat`：基于 Conversation 历史和现有文本 LLM 能力执行同步、多轮、仅文本的基础对话轮次。

### Modified Capabilities

- 无。

## Impact

- 新增 `app/modules/dialogue` 及 `app/composition/dialogue.py`，由 Dialogue Runtime 依赖 Conversation 应用服务和 LLM Port。
- 扩展 `app/modules/llm/contracts.py` 和 OpenAI-compatible Chat 适配器的内部消息映射；V1 HTTP 请求/响应契约不变。
- 复用现有 PostgreSQL Conversation 写入和读取能力，不新增表、迁移、Redis 或缓存。
- LLM 调用和数据库写入跨越外部边界，首版不承诺原子性、幂等重试、Turn/Event 记录或恢复执行。
