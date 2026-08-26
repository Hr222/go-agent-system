## Context

`ARCHITECTURE.md` 要描述系统已批准的完整架构设计，README 要让使用者理解项目和运行方式。它们不能再承担系统看板的实际进度职责，也不能替代 OpenSpec 的需求、任务和验收记录。

代码的物理布局已采用 `app/platform`、`app/business` 与 `interfaces`、`infrastructure`、`composition`、`shared` 四个横向技术层。文档仍需校正若干语义：Gateway 不是所有 HTTP 请求的中转层；Ingestion 不是政策业务模块；`online` 和 Tender 不是平台能力；Agent Runtime 属于 Agent Management 的受控执行结构。

多轮上下文采用 `streaming-chat-multiturn-context` 已确认的完成态作为架构设计前提。本 Change 只消费这一设计，不实施或扩展上下文功能。

## Goals / Non-Goals

**Goals:**

- 让 `ARCHITECTURE.md` 成为完整、稳定且自洽的系统架构设计。
- 清楚呈现平台能力、业务应用与横向技术层，以及迁移后的物理目录。
- 通过有限的图示准确表达入口分支、Agent 受控调用、资料处理与多轮上下文链路。
- 让 README 提供面向使用者的项目说明和运行导航，并把详细架构解释收敛到 `ARCHITECTURE.md`。

**Non-Goals:**

- 不修改应用代码、接口、数据库、前端、外部 Provider 或部署配置。
- 不把 `ARCHITECTURE.md` 写成项目进度表、历史记录、变更日志或未来路线图。
- 不在本 Change 中设计或实施 Task Management、Workflow、多 Agent、低代码编辑器，或额外的上下文记忆机制。
- 不修改系统看板的职责和内容。

## Decisions

### 1. 按文档职责分离架构、进度和交付过程

`ARCHITECTURE.md` 描述完整的系统架构设计，包括稳定的模块边界、依赖方向和关键链路。`docs/go agent system - 系统看板.md` 描述实际进度与优先级。OpenSpec Change 描述一次交付的需求、设计、任务和验证。

因此架构文档不出现“进行中”“尚未上线”等进度措辞，不保留历史迁移叙述，也不预先列出未来能力。架构设计发生实质变化时，以新的完整设计替换或更新对应内容。

### 2. 同时呈现语义分层和物理分层

架构文档先从语义上区分：

```text
平台能力层：LLM、Knowledge/RAG、Ingestion、Conversation、Dialogue、Interaction、
            Agent Management、Attachment、Security
业务应用层：online、agents/tender
横向技术层：interfaces、infrastructure、composition、shared
```

再使用迁移后的目录解释物理归属。`AgentCallDispatcher` 虽由 Interaction 中的应用服务承载，但它、Capability Catalog、Agent Call Policy 与 Agent Runtime 共同构成 Agent Management 的受控执行结构。这样既保留代码位置，也不把运行时职责错误拆成独立的平台能力。

### 3. 在总体图中区分请求入口与对象组装

总体图使用两条运行时路径：

- 直接 HTTP 路由调用相应的 Application Capability，例如资料、知识、会话和附件能力；Security 在需要时提供 `RequestPrincipal`，但请求不经过 Gateway。
- 自然语言 Chat 经 `InteractionChatStreamApplication` 进入 Gateway，由 Capability Catalog、确认策略和后续分发选择 Dialogue 或 Agent 分支。

Composition Root 以虚线连接各组件，明确其职责是注入适配器、组装对象和固定分发绑定，不是请求中继层。这样保留现有直接接口，同时说明 Gateway 作为自然语言控制面的边界。

### 4. 用受控链路表达 Agent Management

Agent 图使用以下顺序：

```text
Chat HTTP
  -> InteractionChatStreamApplication
  -> Gateway / Capability Catalog
  -> confirmation policy
  -> DialogueAgentInvocation
  -> AgentCallDispatcher
  -> Agent Runtime
  -> Tender
  -> DialogueAgentContinuation
  -> LLM
```

Capability Catalog 与策略先复核可调用目标和调用条件，`AgentCallDispatcher` 再执行固定绑定的分发。客户端或模型都不能直接指定执行目标。Tender 是该链路上的业务 Agent 示例，其结构化 LLM、附件、文档读取和渲染依赖不延伸为平台能力。

### 5. 分开 Ingestion、Knowledge/RAG 与业务实现

Ingestion 是平台级资料处理 Pipeline：它通过 Knowledge 写入能力持久化处理结果，并通过 LLM Embedding Port 获得向量化能力。政策资料是该 Pipeline 的验证样本，不改变其通用归属。

`online` 通过 Knowledge Query/RAG 和自身的 `AnswerGenerator` Port 使用检索结果，不直接依赖 LLM 平台包。Tender 不连接 Knowledge/RAG，图中不得绘制 `Tender -> Knowledge` 边。

### 6. 以确认的完成态呈现多轮上下文

Conversation 和 Dialogue 的上下文图固定表达为：

```text
Conversation history
  -> History Read Service
  -> Context Builder（连续的近期窗口与成本预算）
  -> ChatLlmRequest.history_messages
  -> LLM
```

当前用户消息在持久化后参与同一 Conversation 的有序历史读取。Context Builder 以 `max_messages=20`、`max_cost=12_000` 选择连续的最近消息后缀，保留历史角色和顺序；当前输入不加入 `history_messages`，而是仅以 `user_prompt` 发送一次。架构文档不得由此推断 Redis、压缩摘要、长期记忆或其他未确认机制。

### 7. README 只保留使用者需要的导航

README 说明项目背景、系统用途、既有能力、目录结构、环境要求、运行指令和已确认的接口访问地址。没有可确认的部署地址时，保留接口访问章节但不虚构地址。详细技术分层、依赖方向和业务图只链接到 `ARCHITECTURE.md`，避免两份文档分别维护架构事实。

## Risks / Trade-offs

- [架构文档与系统看板重新重叠] → 用明确的文档职责和验收清单限制两者内容。
- [图把语义关系误写成物理依赖] → 每条图边同时依据代码调用位置或已确认的关联 Change 设计复核。
- [把上下文 Change 的设计扩展为未确认能力] → 仅采用已确认的历史读取、窗口、预算和请求装配规则。
- [README 再次复制详细架构] → README 只保留摘要与链接，详细解释只存在于 `ARCHITECTURE.md`。

## Migration Plan

1. 汇总迁移后代码布局与关联 Change 中已确认的术语、入口和调用事实。
2. 重写 `ARCHITECTURE.md` 的定位、分层、目录说明、关键模块文字和四张图。
3. 更新 README 的项目说明、能力摘要、目录导航、运行与接口访问章节，并链接架构文档。
4. 对照代码和确认设计审阅所有图边、路径、模块名和 Markdown 链接，运行文档与 OpenSpec 检查。

无需运行时或数据迁移。文档变更可通过版本控制回退。

## Open Questions

无。
