# 项目进度看板

## 1. 文档职责

本文档只记录项目交付状态、已完成 Change、当前验证和待办，不定义系统架构、模块边界、接口契约或技术选型。

当前系统架构唯一依据是 [`ARCHITECTURE.md`](../ARCHITECTURE.md)。模块职责、依赖方向、后端与前端结构以及当前能力边界均在该文档维护；本看板不重复描述。

具体需求、设计、任务和验收条件以对应的 OpenSpec Change 为准。已完成 Change 位于 [`openspec/changes/archive/`](../openspec/changes/archive/)，当前 Change 位于 [`openspec/changes/`](../openspec/changes/)。

## 2. 当前状态

当前项目已完成上下文管理和 Task Management 的 TM-04 Worker 执行能力。知识库、RAG、规则判断、LLM、统一交互、Tender Agent、附件和会话能力已经形成可运行链路；最近一组交互稳定性 Change 已完成实现、验证和归档。

| 领域 | 状态 | 当前进度 |
|---|---|---|
| 知识库与文档入库 | 已完成基础链路 | 文档解析、OCR、清洗、切分、Embedding、入库、发布、检索和引用可用。 |
| RAG 与规则判断 | 已完成基础链路 | 支持混合检索、证据引用、资料不足判断和材料核验场景。 |
| LLM 与流式交互 | 已完成基础链路 | 支持 Chat、结构化输出、Embedding、Provider 适配、SSE、重试、限流和并发治理。 |
| Interaction 与 Agent | 已完成基础链路 | 支持能力目录、候选识别、确认、受控分发和 Tender Agent 调用。 |
| 附件与产物 | 已完成基础链路 | 支持上传、主体/会话访问绑定、Tender 输入解析和受控下载。 |
| Conversation 与 Dialogue | 已完成当前交付 | 支持会话持久化、历史读取、列表管理、话题概括、主体隔离、轮次串行、Agent 异步执行、上下文管理和异步持久化。 |
| Task Management | 当前阶段 | TM-01 状态机、TM-02 PostgreSQL 持久化、TM-03 受信任内部提交和 TM-04 Worker 执行均已完成；租约恢复、HTTP 和业务接入仍待后续 Change。 |
| Workflow / Agent 平台 | 后续阶段 | 第三阶段，位于 Task Management 之后；当前前端仅有 Workflow mock，真实编排能力尚未实施。 |
| 真实身份认证与用户模块 | 待规划 | 不作为当前验收项，具体边界以 `ARCHITECTURE.md` 的当前边界为准。 |

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
| `fix-interaction-stream-resource-lifecycle` | `eff266f` | 已完成并归档 |
| `fix-interaction-sync-boundaries-and-cancellation` | `21ae687` | 已完成并归档 |
| `submit-trusted-tasks` | `f2a26c2` | 已完成并归档 |
| `persist-task-lifecycle` | `14a8684` | 已完成并归档 |
| `claim-task-worker-leases` | 待提交 | 实现与验证完成，待归档和提交 |

`persist-task-lifecycle` 已将 TM-01 的 Task、Attempt、Event 和命令回执持久化到 PostgreSQL；TM-04 已补充受信任 Worker 的原子领取、lease 续租、固定执行器和安全结果回写，但不实现租约恢复、HTTP、业务接入或前端。TM-01“任务状态机与幂等”及其契约收紧均已完成并归档；同一时间只处理一个 Task Management Change。
已完成 Change 的完整工件位于 [`openspec/changes/archive/`](../openspec/changes/archive/)。

## 5. 当前验证

最近一组 Change 的后端验收结果：

TM-04 相关测试与全量验证：`python -m pytest -q` 为 `738 passed`；Worker、PostgreSQL 并发和架构边界测试均通过；`ruff check app tests`、`python -m compileall -q app tests`、`git diff --check` 和 `openspec validate --all --strict` 均通过。外部 LLM、Embedding、OCR、MCP 和浏览器链路仍需使用项目现有诊断脚本或人工验收记录，不能只凭单元测试宣称外部服务验收完成。

## 6. 后续能力优先级

以下只记录能力优先级，不提前定义未来架构。具体实施时分别创建独立的 OpenSpec Change：

| 优先级 | 能力 | 状态 |
|---|---|---|
| 1 | 上下文管理 | 已完成；会话历史、上下文窗口和多轮上下文链路已交付。 |
| 2 | Task Management | TM-01～TM-04 已完成；下一步进入租约恢复、取消与重试 Change。 |
| 3 | Workflow / Agent 平台 | 后续阶段；依赖 Task Management，尚未实施真实编排引擎。 |
| 4 | 真实认证与用户模块 | 待规划；尚未创建 Change。 |

### Task Management Change 顺序（占位）

以下只记录实施顺序、依赖和验收目标。TM-09 当前只保留空目录名称占位，不含 OpenSpec 工件、任务或实现；其余后续项仅记录在本表。必须在前置 Change 完成、验证和归档后，才逐个创建各自的 proposal、design、specs 和 tasks。

| 顺序 | 占位 Change | 依赖 | 本阶段验收目标 | 状态 |
|---|---|---|---|---|
| TM-01 | `define-task-state-machine-and-idempotency` | 无 | 明确 Task、Attempt、Event 的状态与转换，以及创建、领取、取消、重试和终态提交的幂等语义。 | 已完成并归档为 `2026-09-18-introduce-task-management`；契约收紧已归档为 `2026-09-18-harden-task-lifecycle-contracts`。 |
| TM-02 | `persist-task-lifecycle` | TM-01 | 将任务、尝试、事件和幂等约束持久化到 PostgreSQL。 | 已完成并归档为 `2026-09-18-persist-task-lifecycle`。 |
| TM-03 | `submit-trusted-tasks` | TM-02 | 提供受信任业务提交契约，不开放浏览器通用创建入口。 | 已完成并归档为 `2026-09-18-submit-trusted-tasks`。 |
| TM-04 | `claim-task-worker-leases` | TM-02 | 以原子领取、lease 和独立 Worker 执行任务。 | 实现与验证完成，待归档和提交。 |
| TM-05 | `recover-cancel-and-retry-tasks` | TM-03、TM-04 | 支持租约恢复、协作式取消与自动/手动重试。 | 占位。 |
| TM-06 | `manage-owned-tasks-over-http` | TM-05 | 提供主体隔离的查询、事件、取消和重试接口。 | 占位。 |
| TM-07 | `run-tender-as-managed-task` | TM-06 | 将 Tender 以受信任提交者和注册执行器接入任务平台。 | 占位。 |
| TM-08 | `connect-task-management-frontend` | TM-06、TM-07 | 以真实 Task API 替换任务页面 mock，支持查询、取消和重试。 | 占位。 |
| TM-09 | `task-management-e2e-integration` | TM-07、TM-08 | 用合成执行器验证浏览器、API、Worker 和 PostgreSQL 的成功、取消、重试、隔离与恢复链路。 | 空目录占位；在 Workflow 前实施。 |
| TM-10 | `orchestrate-task-workflows` | TM-09 | 基于已验证的单任务能力设计多任务编排。 | 占位。 |

## 7. 当前待办

1. 完成 TM-04 的全量验证、归档和远程提交；不得与其他 Task Management Change 并行展开。
2. TM-05 继续处理租约恢复、协作式取消和自动/手动重试。
3. 根据实际代码和验证结果持续同步 OpenSpec 正式规格并归档已完成 Change。
4. 系统架构发生实际变化时更新 [`ARCHITECTURE.md`](../ARCHITECTURE.md)；看板只更新状态和验收记录，不新增架构副本。

## 8. 相关文档

- [`ARCHITECTURE.md`](../ARCHITECTURE.md)：当前唯一系统架构。
- [`README.md`](../README.md)：项目定位、当前能力、运行方式和访问入口。
- [`agent.md`](../agent.md)：协作、工程开发、测试、安全和 Git 约定。
- [`openspec/README.md`](../openspec/README.md)：OpenSpec 工作流和 Change 约定。
- [`tools/ocr/README.md`](../tools/ocr/README.md)：OCR 与样本分类工具说明。
