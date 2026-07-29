# Phase 3 F1 过渡桥接

> 状态：临时过渡文件。Phase 3 完成并删除两份阶段文档后，本文件可以归档或删除。

## 目的

本文件记录项目从既有阶段文档逐步迁移到 OpenSpec 时的边界，避免把尚未完成的 Phase 3 计划误写成已存在的 OpenSpec 能力规格。

当前策略是：

- 已建立的 Chat 流式 Change 继续按 OpenSpec 的同步和归档流程收口。
- 尚未完成的 Phase 3 Tender 垂直切片暂由两份阶段文档管理：总计划是联合蓝本，联合进度文档记录前后端执行明细和证据。
- Phase 3 完成后，两份阶段文档一并删除；后续阶段的详细工作从 OpenSpec Explore/Change 开始管理，系统看板仅保留高层状态。

## 文档职责

| 文档 | 当前职责 |
| --- | --- |
| `docs/go agent system - 系统看板.md` | 项目定位、阶段状态和后续方向。 |
| `docs/第三阶段工作计划.md` | Phase 3 前后端联合蓝本：统一范围、依赖、状态和验收标准。 |
| `docs/第三阶段- 前后端联合工作进度.md` | Phase 3 唯一执行进度记录：前后端工作包、实现证据、测试、联调和人工验收。 |
| `openspec/changes/*` | 已建立 Change 的规格、任务、验证与归档过程；不自动代表整个 Phase 3。 |

## 当前映射

| 内容 | 管理位置 | 当前状态 |
| --- | --- | --- |
| F1-A：通用 LLM 单轮技术验证 | 已归档的 `complete-llm-chat-acceptance` Change 与两份阶段文档中的实施证据 | 已完成。 |
| Chat 流式与打字机展示 | `llm-chat-streaming`、`improve-chat-stream-visibility`、`add-chat-stream-pacing` | 实现与验证已完成，待按顺序同步规格和归档。 |
| Tender 同步文件/RAG/LLM 前后端闭环 | 两份 Phase 3 阶段文档 | 未开始，是 Phase 3 剩余工作。 |
| Task Management | 后续独立阶段与 OpenSpec Change | 不属于 Phase 3。 |
| Conversation / Context Management | 后续独立阶段与 OpenSpec Change | 不属于 Phase 3。 |
| 多 Agent 编排 | 后续独立阶段与 OpenSpec Change | 不属于 Phase 3。 |

## 过渡规则

1. Phase 3 的范围、联合验收和总体状态更新到 `第三阶段工作计划.md`；前后端的实现事实、测试和人工证据统一更新到联合进度文档。
2. 两份文档的范围和状态必须互相核对；联合进度证据改变总体结论时，同步更新联合蓝本。
3. 不把“尚未开始的计划”伪装成正式 Change 或正式规格；既有 Change 只描述其实际覆盖的能力。
4. Phase 3 完成后，提炼需要保留的结论并删除两份阶段文档和本桥接文件；从下一阶段起，先按需要 Explore，再建立独立 Change。
