## Context

`llm-dialogue-system-v2` 最初仅是依赖路线图。Conversation 基础、Dialogue Runtime、Interaction 控制、结构化 Agent 调用、对话中的 Agent 结果续写及 V1 入口退场已分别通过 14 个独立 Change 实现和归档。母 Change 缺少正式 artifacts，导致其无法作为 OpenSpec Change 被严格校验。

本设计只补齐顶层收口记录。行为实现仍以叶子 Change 和已生效的主规格为准，母 Change 不重新定义它们的内部接口或替换其测试。

## Goals / Non-Goals

**Goals:**

- 建立一个可验证的 V2 端到端组合契约。
- 说明普通对话、显式确认后的 Agent 调用、结果续写和旧入口退场之间的关系。
- 使母 Change 的 artifacts、任务状态和当前实现验证结果保持一致。

**Non-Goals:**

- 不新增 Agent 能力、任务管理、重试队列、工作流或多 Agent 编排。
- 不修改 Conversation、Dialogue、Interaction、LLM Provider 或持久化实现。
- 不取代叶子 Change 的细化规格、设计和测试。

## Decisions

### 1. 母 Change 只定义端到端组合行为

顶层规格聚焦调用方可观察到的 V2 行为：从 Interaction Chat 入口发起对话、显式确认 Agent 调用、获得最终回答和安全结果摘要，以及旧入口不可用。具体领域规则继续由现有能力规格维护。这样既能形成完整验收面，又避免重复复制 14 份行为契约。

### 2. 使用已归档叶子 Change 作为实现追溯来源

任务逐项引用已归档 Change，而不是在母 Change 中重新列出代码文件或实现步骤。叶子 Change 已包含实现、边界测试和归档证据；母 Change 只验证它们按路线图依赖顺序共同构成 V2 对话系统。

### 3. 以当前自动化校验作为收口证据

收口任务要求后端测试、前端测试、前端构建、Python 编译和 OpenSpec 严格校验通过。全量 Ruff 的三个既有测试文件问题单独记录，不能被误写为本 Change 已通过的检查。

## Risks / Trade-offs

- [顶层规格与叶子规格重复或漂移] -> 顶层只描述组合行为，细化规则仍链接到已生效的叶子能力规格。
- [已归档记录和当前实现出现偏差] -> 通过全量后端、前端和 OpenSpec 校验发现回归；后续行为变更必须建立新的叶子 Change。
- [历史 Ruff 问题掩盖本 Change 状态] -> 在任务中明确其文件范围和未纳入“全量 Ruff 通过”的结论。

## Migration Plan

无需部署、数据迁移或回滚。此 Change 仅补齐 OpenSpec artifacts；如果需要撤销，只删除本母 Change 新增的收口文档，不影响已归档叶子 Change 或运行时代码。

## Open Questions

无。
