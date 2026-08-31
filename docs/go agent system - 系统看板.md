# 项目进度看板

## 1. 文档职责

本文档只记录项目交付状态、已完成 Change、当前验证和待办，不定义系统架构、模块边界、接口契约或技术选型。

当前系统架构唯一依据是 [`ARCHITECTURE.md`](../ARCHITECTURE.md)。模块职责、依赖方向、后端与前端结构以及当前能力边界均在该文档维护；本看板不重复描述。

具体需求、设计、任务和验收条件以对应的 OpenSpec Change 为准。已完成 Change 位于 [`openspec/changes/archive/`](../openspec/changes/archive/)，当前 Change 位于 [`openspec/changes/`](../openspec/changes/)。

## 2. 当前状态

当前项目处于平台能力整合与稳定性验证阶段。知识库、RAG、规则判断、LLM、统一交互、Tender Agent、附件和会话能力已经形成可运行链路；最近一组普通流式对话 Change 已完成实现、验证和归档。

| 领域 | 状态 | 当前进度 |
|---|---|---|
| 知识库与文档入库 | 已完成基础链路 | 文档解析、OCR、清洗、切分、Embedding、入库、发布、检索和引用可用。 |
| RAG 与规则判断 | 已完成基础链路 | 支持混合检索、证据引用、资料不足判断和材料核验场景。 |
| LLM 与流式交互 | 已完成基础链路 | 支持 Chat、结构化输出、Embedding、Provider 适配、SSE、重试、限流和并发治理。 |
| Interaction 与 Agent | 已完成基础链路 | 支持能力目录、候选识别、确认、受控分发和 Tender Agent 调用。 |
| 附件与产物 | 已完成基础链路 | 支持上传、主体/会话访问绑定、Tender 输入解析和受控下载。 |
| Conversation 与 Dialogue | 已完成当前交付 | 支持会话持久化、历史读取、列表管理、话题概括、主体隔离、轮次串行、Agent 异步执行、上下文窗口和异步持久化。 |
| 真实身份认证与多 Agent 编排 | 当前未实施 | 不作为当前验收项，具体边界以 `ARCHITECTURE.md` 的当前边界为准。 |

## 3. 已完成 Change

以下为当前平台能力的主要已完成交付，完整归档记录以 [`openspec/changes/archive/`](../openspec/changes/archive/) 为准：

| 交付组 | 已完成内容 |
|---|---|
| 知识库与检索 | 知识查询、写入、发布、混合检索、rerank、HNSW、规则判断和入库流水线。 |
| LLM 与 Chat | 流式 Chat、Provider 接入、结构化输出归一化、流式展示、重试、限流和 GLM 配置分离。 |
| Interaction 与 Agent | 意图候选召回、能力目录、结构化识别、确认策略、受控 Agent 分发、Tender MCP 和分块分析。 |
| Conversation 与 Dialogue | 会话模型与存储、主体范围创建/列表/历史、流式持久化、Agent 续写、会话管理和附件输入。 |
| 安全与附件 | RequestPrincipal、HTTP 主体绑定、会话 owner 隔离、附件访问绑定、Tender 附件适配和 Agent 产物下载。 |
| 架构文档 | `ARCHITECTURE.md` 作为当前系统架构唯一来源，阶段看板不再复制架构内容。 |

## 4. 最近完成的 Change

| Change | Commit | 状态 |
|---|---|---|
| `serialize-streaming-conversation-turns` | `270a9a8` | 已完成并归档 |
| `make-agent-turn-execution-asynchronous` | `a92b7eb` | 已完成并归档 |
| `serialize-agent-continuation-turns` | `a3240f7` | 已完成并归档 |
| `stabilize-conversation-context-window` | `6d07003` | 已完成并归档 |
| `make-conversation-persistence-asynchronous` | `a61715c` | 已完成并归档 |

当前没有活动中的 Change；完整工件位于 [`openspec/changes/archive/`](../openspec/changes/archive/)。

## 5. 当前验证

最近一组 Change 的后端验收结果：

`python -m pytest -q`：`650 passed`；PostgreSQL 交界测试：`1 passed`；`ruff check app tests`、`python -m compileall -q app tests`、`git diff --check` 和相关 OpenSpec strict validate 均通过。

外部 LLM、Embedding、OCR、MCP 和浏览器链路还需要使用项目现有的诊断脚本或人工验收记录结果；不能只凭单元测试宣称外部服务验收完成。

## 6. 后续能力优先级

以下只记录能力优先级，不提前定义未来架构。具体实施时分别创建独立的 OpenSpec Change：

| 优先级 | 能力 | 状态 |
|---|---|---|
| 1 | 上下文压缩与摘要 | 当前优先项；现有 `streaming-chat-multiturn-context` 提供历史上下文基础，但尚未包含摘要、压缩或 Compaction。 |
| 2 | Task Management | 待规划；尚未创建 Change。 |
| 3 | 多 Agent / Workflow | 待规划；尚未创建 Change。 |
| 4 | 真实认证与用户模块 | 待规划；尚未创建 Change。 |

## 7. 当前待办

1. 为上下文压缩与摘要创建独立 OpenSpec Change，并在范围明确后实施。
2. 评估 Task Management 的实际需求和异步任务生命周期。
3. 根据实际代码和验证结果持续同步 OpenSpec 正式规格并归档已完成 Change。
4. 系统架构发生实际变化时更新 [`ARCHITECTURE.md`](../ARCHITECTURE.md)；看板只更新状态和验收记录，不新增架构副本。

## 8. 相关文档

- [`ARCHITECTURE.md`](../ARCHITECTURE.md)：当前唯一系统架构。
- [`README.md`](../README.md)：项目定位、当前能力、运行方式和访问入口。
- [`agent.md`](../agent.md)：协作、工程开发、测试、安全和 Git 约定。
- [`openspec/README.md`](../openspec/README.md)：OpenSpec 工作流和 Change 约定。
- [`tools/ocr/README.md`](../tools/ocr/README.md)：OCR 与样本分类工具说明。
