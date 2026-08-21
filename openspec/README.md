# OpenSpec 使用约定

## 定位

OpenSpec 是本项目的需求变更与验收契约层，用于明确“要改变什么、为什么改变、什么结果算完成”。

它不替代现有文档：

| 文档 | 职责 |
|---|---|
| `agent.md` | AI 协作、编码和验证纪律 |
| `ARCHITECTURE.md` | 后端与前端架构、模块职责、依赖边界和前后端交互边界 |
| `docs/` | 阶段目标、调研笔记、实施进度和历史记录 |
| `openspec/specs/` | 已生效的业务能力契约 |
| `openspec/changes/` | 正在进行的需求变更及其验收材料 |

## Brownfield 规则

本项目是已有代码库，不要求一次性为全部功能补齐规格。按照 delta-first 方式，只为当前要修改的能力建立变更规格；完成并归档后，再将有效的行为增量合并到正式规格中。

不要把 `README.md`、架构文档或阶段计划直接复制到 `openspec/specs/`。OpenSpec 规格应描述可观察行为、业务约束和验收场景。

## 什么时候必须创建 Change

以下变更必须先创建 OpenSpec change：

- 修改 HTTP 请求或响应契约；
- 修改数据库结构、持久化语义或数据迁移；
- 修改业务规则、任务状态或错误处理；
- 修改跨模块依赖、端口或外部 Provider；
- 修改 RAG 引用、证据不足或规则判断行为；
- 增加前后端联动能力、异步任务或重试机制；
- 涉及权限、安全、审计或敏感数据。

纯样式调整、行为不变的局部重构、文档错别字和独立测试补充，可以不创建完整 change。

## 推荐工作流

当前 Codex 界面没有注册 `/opsx:*` 斜杠命令。项目使用“终端 CLI 管理 Change + Codex 普通对话生成和实现 artifacts”的方式：

```powershell
$cli = Join-Path ((npm.cmd prefix -g).Trim()) "openspec.cmd"

# 创建 Change 目录
& $cli new change <change-name> --description "简短描述" --goal "完成目标"

# 查看 artifacts 是否齐全
& $cli status --change <change-name> --json

# 严格校验所有 Change
& $cli validate --all --strict --no-interactive

# 完成并归档 Change
& $cli archive <change-name>
```

创建目录后，在 Codex 中直接用普通消息说明需求，例如：“请基于当前 F1 过渡桥，为 `tender-agent-input` 创建 proposal、specs、design 和 tasks，严格排除 Task Management、Conversation、F2 和完整 Tender Agent。” Codex 再根据需求写入 artifacts。

开始实现前必须阅读当前 Change 的 proposal、specs、design 和 tasks。实现过程中如果发现目标、边界或验收条件发生变化，应先更新 Change artifacts，再继续修改代码。

## 验收要求

OpenSpec 的 Scenario 必须能对应到自动化测试、架构检查、前端构建或明确的人工验收证据。项目常用验证命令如下：

```powershell
python -m pytest -q
ruff check app tests
python -m compileall -q app tests
cd frontend
npm run build
```

涉及 RAG 或业务判断时，还必须验证来源追踪、证据不足和失败分支；不能只验证正常返回。

## 当前接入边界

OpenSpec 已完成基础接入，并已通过 `complete-llm-chat-acceptance` 固化 F1-A 的独立 LLM 单轮对话验收。后续从 F1 的下一个 Step 开始，需求、行为契约、设计、任务和验收证据统一通过独立 Change 管理。

F1 后续按纵向 Step 拆分，不创建覆盖整个 Tender Agent 的大 Change。Tender Agent 入口、文件准入、结构化 Prompt 和骨架生成分别在范围明确后建立对应 Change。

Conversation（历史消息和上下文）与 Task Management（任务生命周期和状态）是与 LLM、Agent 同级的独立模块，不纳入当前 LLM Change，也不在 LLM 或 Agent 模块内部隐式实现；它们未来分别建立独立 Change。

## Phase 3 文档过渡

当前两份 F1 阶段文档尚未完成迁移，过渡规则和内容映射见 [`context/phase3-f1-transition-bridge.md`](context/phase3-f1-transition-bridge.md)。它们暂时保留为历史和阶段基线；后续新增工作统一进入 OpenSpec Change，满足桥接文件中的删除条件后再移除原文档。
