## Why

V2 LLM 对话能力已由多个独立 Change 分阶段交付，但顶层目录只保留了路线图，无法作为可验证的整体变更通过 OpenSpec 校验。需要将已落地的端到端行为、子 Change 追溯关系和收口验收正式化。

## What Changes

- 新增 V2 对话系统端到端能力规格，明确普通对话、受控 Agent 调用和旧 LLM Chat 入口退场后的可观察行为。
- 将母 Change 说明更新为已完成的子 Change 汇总，而不是未来计划。
- 记录只做规格与验收收口；不新增运行时代码、HTTP 路由、数据库迁移或外部依赖。

## Capabilities

### New Capabilities

- `dialogue-system-v2-release`: 定义 V2 对话入口、确认后的 Agent 结果和旧入口退场组成的端到端行为。

### Modified Capabilities

- 无。

## Impact

- 新增母 Change 的 proposal、design、spec 和 tasks，用于汇总 14 个已归档叶子 Change。
- 规格引用现有的 Conversation、Dialogue、Interaction 与 Agent 能力；不改变其公开 HTTP 契约、持久化结构、状态流转、Provider 调用或安全边界。
- 现有 V2 前端 Chat 页面继续使用 Interaction 流式入口；旧 `/api/v1/llm/chat` 与 `/api/v1/llm/chat/stream` 保持退场状态。
