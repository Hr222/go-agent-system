# Phase 3 F1 过渡桥接

> 状态：临时过渡文件。两份阶段文档完成迁移并满足本文删除条件后，再删除本文件。

## 目的

本文件用于把 Phase 3 F1 的现有阶段文档接入 OpenSpec 的工作流。它不复制阶段文档全文，也不把尚未实现的计划伪装成正式能力规格。

过渡期间：

- 阶段文档保留历史背景、原始计划和迁移前进度。
- OpenSpec Change 负责当前正在实施的需求、行为契约、设计、任务和验收证据。
- `ARCHITECTURE.md`、`agent.md` 和 `FRONTEND_ARCHITECTURE.md` 继续负责长期工程约束。

## 来源文档

| 来源 | 过渡期职责 | 后续替代位置 |
|---|---|---|
| `docs/第三阶段- 后端F1工作进度.md` | 后端 F1 的历史进度、工作包、遗留问题和阶段结论 | 各 F1 Step 对应 Change 的 `proposal.md`、`design.md`、`tasks.md` 和验证证据 |
| `docs/第三阶段 - 前端改造工作.md` | 前端工作包、页面规划、联调记录和人工验收背景 | 各 Change 的前端影响、任务和构建/人工验收证据 |

## 当前映射

| 原阶段内容 | OpenSpec 归属 | 当前状态 |
|---|---|---|
| F1-A / FE-LLM-01：独立 LLM 单轮技术验证 | `complete-llm-chat-acceptance` | 已完成验收；不代表 F1 整体完成 |
| F1-B：Tender Agent 输入和文件准入 | 后续独立 Change，建议名称 `tender-agent-input` | 未开始 |
| F1-C：Task Management | 后续独立 Change，建议名称 `task-management` | 暂不纳入当前 F1 |
| F1-D：结构-only 投标书骨架 | 后续独立 Change，名称待范围确认 | 未开始 |
| Conversation：历史消息和上下文 | 后续独立 Change，名称待范围确认 | 不属于当前 LLM Change 或 Agent Change |

## 迁移规则

1. 新的 F1 工作不再直接追加到两份阶段进度文档；先创建对应 OpenSpec Change。
2. 每个 Change 只覆盖一个可评审、可验证的 Step，不创建覆盖整个 Tender Agent 的大 Change。
3. 阶段文档中的计划条目只有在进入实施时，才迁移为 proposal、spec、design 和 tasks；未开始条目继续保留为背景，不标记为已完成。
4. OpenSpec 的 Scenario 必须映射到自动化测试、架构检查、前端构建或明确的人工验收证据。
5. Conversation 和 Task Management 作为与 LLM、Agent 同级的独立模块，不能隐式并入 LLM 或 Agent Change。

## 删除两份阶段文档前的条件

只有全部条件满足后，才删除两份阶段进度文档：

- 每个仍然有效的 F1 工作包都已经映射到一个 OpenSpec Change 或被明确标记为暂缓/取消。
- 已实施 Change 的 `tasks.md` 已记录完成任务和验证证据。
- 已完成 Change 已归档，正式规格已经保留仍然有效的行为契约。
- OpenSpec 中已经能够追踪 F1 当前状态、遗留问题和下一步，不再依赖阶段文档正文。
- 删除阶段文档不会破坏 proposal、design、spec 或 README 中的必要引用；引用已迁移到长期架构文档、正式规格或本桥接文件的归档记录。
- 删除动作单独提交，便于审查和恢复。

在上述条件满足前，不删除原文档，也不把本桥接文件当作正式业务规格。
