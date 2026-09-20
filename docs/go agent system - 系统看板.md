# 项目进度看板

## 1. 文档职责

本文档只记录项目交付状态、已完成 Change、当前验证和待办，不定义系统架构、模块边界、接口契约或技术选型。

当前系统架构唯一依据是 [`ARCHITECTURE.md`](../ARCHITECTURE.md)。模块职责、依赖方向、后端与前端结构以及当前能力边界均在该文档维护；本看板不重复描述。

具体需求、设计、任务和验收条件以对应的 OpenSpec Change 为准。已完成 Change 位于 [`openspec/changes/archive/`](../openspec/changes/archive/)，当前 Change 位于 [`openspec/changes/`](../openspec/changes/)。

## 2. 当前状态

当前项目已完成上下文管理和 Task Management 的 TM-07.4 Tender 异步 Consumer，并正在收口独立 Worker 与 Dialogue 已接收交接。知识库、RAG、规则判断、LLM、统一交互、Tender Agent、附件和会话能力已经形成可运行链路；外部 Tender MCP 保持同步，内部 Dialogue 使用异步 Task。

| 领域 | 状态 | 当前进度 |
|---|---|---|
| 知识库与文档入库 | 已完成基础链路 | 文档解析、OCR、清洗、切分、Embedding、入库、发布、检索和引用可用。 |
| RAG 与规则判断 | 已完成基础链路 | 支持混合检索、证据引用、资料不足判断和材料核验场景。 |
| LLM 与流式交互 | 已完成基础链路 | 支持 Chat、结构化输出、Embedding、Provider 适配、SSE、重试、限流和并发治理。 |
| Interaction 与 Agent | 已完成基础链路 | 支持能力目录、候选识别、确认、受控分发和 Tender Agent 调用。 |
| 附件与产物 | 已完成基础链路 | 支持上传、主体/会话访问绑定、Tender 输入解析和受控下载。 |
| Conversation 与 Dialogue | 已完成当前交付 | 支持会话持久化、历史读取、列表管理、话题概括、主体隔离、轮次串行、Agent 异步接收状态、上下文管理和异步持久化；`accepted` 只返回安全 execution reference，不自动回灌终态消息。 |
| Task Management | 当前阶段 | TM-01～TM-07.4 已完成并归档；当前 Change 增加独立 Tender Worker 入口和 Dialogue `accepted` 交接。外部 Tender MCP 仍同步返回 `EmbeddedResource`；Task 结果下载、任务前端和 E2E 尚未立项。 |
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
| `claim-task-worker-leases` | `5b8bd49` | 已完成、已归档并推送远程 |
| `recover-cancel-and-retry-tasks` | `44867c4` | 已完成、已归档并推送远程 |
| `manage-owned-tasks-over-http` | 本 Change 提交 | 已完成、已归档并推送远程 |
| `define-agent-call-extension-seam` | `62cb96e` | 已完成并归档；远程推送待网络恢复 |
| `route-tender-mcp-through-agent-dispatch` | `d134d31` | 已完成并归档；远程推送待网络恢复 |
| `bridge-agent-calls-to-tasks` | `0be9951` | 已完成并归档；远程推送待网络恢复 |
| `run-tender-agent-as-async-task` | `e06c81c` | 已完成并归档；外部 MCP 同步边界已由 `restore-tender-mcp-sync-boundary` 收口 |
| `complete-internal-tender-task-handoff` | 当前工作区 | 实现独立 Tender Worker、Dialogue `accepted` 与安全 execution reference；不包含下载、Workflow 或终态会话回传 |

`persist-task-lifecycle` 已将 TM-01 的 Task、Attempt、Event 和命令回执持久化到 PostgreSQL；TM-04 已补充受信任 Worker 的原子领取、lease 续租、固定执行器和安全结果回写；TM-05 已补充过期 lease 恢复、协作取消、退避重入队和受策略约束的手动重试；TM-06 已补充主体隔离的 Task/事件查询、协作取消和手动重试 HTTP 契约，但不实现 Tender、前端或 E2E。TM-01“任务状态机与幂等”及其契约收紧均已完成并归档；同一时间只处理一个 Task Management Change。
已完成 Change 的完整工件位于 [`openspec/changes/archive/`](../openspec/changes/archive/)。

## 5. 当前验证

最近一组 Change 的后端验收结果：

TM-04 相关测试与全量验证：`python -m pytest -q` 为 `738 passed`；TM-05 完成后为 `750 passed`；TM-06 完成后为 `763 passed`；TM-07.2 完成后为 `769 passed`；TM-07.3 完成后为 `781 passed`；TM-07.4 完成后为 `793 passed`；当前 `complete-internal-tender-task-handoff` 完成后为 `803 passed`，另有 2 个既有弃用警告。聚焦测试为 `48 passed`；`ruff check app tests`、`python -m compileall -q app tests`、前端 `npm run build`、严格 OpenSpec 校验和 `git diff --check` 均通过。外部 LLM、Embedding、OCR、MCP 和浏览器链路仍需使用项目现有诊断脚本或人工验收记录，不能只凭单元测试宣称外部服务验收完成。

## 6. 后续能力优先级

以下只记录能力优先级，不提前定义未来架构。具体实施时分别创建独立的 OpenSpec Change：

| 优先级 | 能力 | 状态 |
|---|---|---|
| 1 | 上下文管理 | 已完成；会话历史、上下文窗口和多轮上下文链路已交付。 |
| 2 | Task Management | TM-01～TM-07.4 已完成；完成当前独立 Worker 与 Dialogue 交接后，再根据真实产品目标规划后续 Change。 |
| 3 | Workflow / Agent 平台 | 后续阶段；依赖 Task Management，尚未实施真实编排引擎。 |
| 4 | 真实认证与用户模块 | 待规划；尚未创建 Change。 |

### Task Management Change 顺序（占位）

以下只记录实施顺序、依赖和验收目标。TM-07 已拆成四个边界清晰的 Change，TM-07.1～TM-07.4 均已完成并归档；当前 Change 收口内部 Tender Worker 与 Dialogue 交接。后续能力必须先根据产品目标另行规划。

| 顺序 | 占位 Change | 依赖 | 本阶段验收目标 | 状态 |
|---|---|---|---|---|
| TM-01 | `define-task-state-machine-and-idempotency` | 无 | 明确 Task、Attempt、Event 的状态与转换，以及创建、领取、取消、重试和终态提交的幂等语义。 | 已完成并归档为 `2026-09-18-introduce-task-management`；契约收紧已归档为 `2026-09-18-harden-task-lifecycle-contracts`。 |
| TM-02 | `persist-task-lifecycle` | TM-01 | 将任务、尝试、事件和幂等约束持久化到 PostgreSQL。 | 已完成并归档为 `2026-09-18-persist-task-lifecycle`。 |
| TM-03 | `submit-trusted-tasks` | TM-02 | 提供受信任业务提交契约，不开放浏览器通用创建入口。 | 已完成并归档为 `2026-09-18-submit-trusted-tasks`。 |
| TM-04 | `claim-task-worker-leases` | TM-02 | 以原子领取、lease 和独立 Worker 执行任务。 | 已完成并归档，提交 `5b8bd49`；远程推送待网络恢复。 |
| TM-05 | `recover-cancel-and-retry-tasks` | TM-03、TM-04 | 支持租约恢复、协作式取消与自动/手动重试。 | 已完成并归档，提交 `2fa78b7`；远程推送待网络恢复。 |
| TM-06 | `manage-owned-tasks-over-http` | TM-05 | 提供主体隔离的查询、事件、取消和重试接口。 | 已完成并归档为 `2026-09-18-manage-owned-tasks-over-http`。 |
| TM-07.1 | `define-agent-call-extension-seam` | TM-06 | 为 AgentCallDispatcher 增加可替换执行策略插口，默认保持同步 AgentRuntime 行为。 | 已完成并归档为 `2026-09-20-define-agent-call-extension-seam`，提交 `62cb96e`；远程推送待网络恢复。 |
| TM-07.2 | `route-tender-mcp-through-agent-dispatch` | TM-07.1 | 将 Tender MCP 三个工具迁移到统一 Agent 分发边界，保持协议兼容并补齐外部主体映射。 | 已完成并归档为 `2026-09-20-route-tender-mcp-through-agent-dispatch`，提交 `d134d31`；远程推送待网络恢复。 |
| TM-07.3 | `bridge-agent-calls-to-tasks` | TM-07.2 | 定义目录能力到异步 Task 的受控桥接、幂等和执行引用，不开放通用 Task 创建。 | 已归档并提交 `0be9951`；`781 passed`、lint、编译和严格 OpenSpec 校验通过；远程推送待网络恢复。 |
| TM-07.4 | `run-tender-agent-as-async-task` | TM-07.3 | 为内部 Tender 调用配置异步档案、输入快照和固定 Executor，接入 Worker、取消、重试和主体隔离。 | 已归档并提交 `e06c81c`；`793 passed`、lint、编译和严格 OpenSpec 校验通过。外部 MCP 同步边界已单独收口。 |

### TM-07 拆分说明

- **TM-07.1 Agent 调用扩展插口**：只改 Agent Management 的分发内部边界。它不迁移 MCP，不接入 Task，也不实现 Workflow；验收重点是授权、错误、附件结果和调用关联字段保持不变，并能注入替身执行策略。
- **TM-07.2 Tender MCP 统一分发**：Tender 仍是一个具体业务 Agent，MCP 适配器只做 Base64、协议结果和错误映射，执行统一交给 AgentCallDispatcher；不把 Tender 变成平台基板。
- **TM-07.3 Agent 到 Task 桥接**：只定义哪些目录能力允许异步以及如何创建受控提交，不直接绑定 Tender，也不暴露通用 Task 创建接口。
- **TM-07.4 Tender 异步 Consumer**：这是第一个真正使用 Task 的业务 Agent Change，复用 TenderApplication 和既有 Task 状态机，不向 Tender 业务层注入 Repository、Session 或 LangGraph。

## 7. 当前待办

1. 完成 `complete-internal-tender-task-handoff` 的独立 Worker、Dialogue `accepted` 交接和全量验证；不要在此之前新增浏览器下载或 Workflow 能力。
2. 根据实际代码和验证结果持续同步 OpenSpec 正式规格并归档已完成 Change。
3. 系统架构发生实际变化时更新 [`ARCHITECTURE.md`](../ARCHITECTURE.md)；看板只更新状态和验收记录，不新增架构副本。

## 8. 相关文档

- [`ARCHITECTURE.md`](../ARCHITECTURE.md)：当前唯一系统架构。
- [`README.md`](../README.md)：项目定位、当前能力、运行方式和访问入口。
- [`agent.md`](../agent.md)：协作、工程开发、测试、安全和 Git 约定。
- [`openspec/README.md`](../openspec/README.md)：OpenSpec 工作流和 Change 约定。
- [`tools/ocr/README.md`](../tools/ocr/README.md)：OCR 与样本分类工具说明。
