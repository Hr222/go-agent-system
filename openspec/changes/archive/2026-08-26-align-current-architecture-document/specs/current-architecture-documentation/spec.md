## ADDED Requirements

### Requirement: 架构文档的职责必须稳定且单一

`ARCHITECTURE.md` MUST 作为完整的系统架构设计，说明稳定的模块边界、依赖方向、关键入口和关键链路。它 MUST NOT 记录交付进度、历史演化、变更日志或未来路线图。系统看板 MUST 承担实际进度与优先级，OpenSpec Change MUST 承担一次交付的需求、任务与验证记录。

#### Scenario: 读者区分三类文档

- **WHEN** 读者同时查阅架构文档、系统看板和本 Change
- **THEN** 能从架构文档获得完整的系统设计
- **AND** 能从系统看板获得实际进度与优先级
- **AND** 能从 OpenSpec 产物获得本次交付的范围和验收任务

### Requirement: 架构文档必须区分语义分层与物理分层

架构文档 MUST 将系统描述为 Agent 开发平台，并区分平台能力层、业务应用层和横向技术层。平台能力层 MUST 包含 LLM、Knowledge/RAG、Ingestion、Conversation、Dialogue、Interaction、Agent Management、Attachment 与 Security；`online` 与 `agents/tender` MUST 作为业务实现呈现。横向技术层 MUST 说明 interfaces、infrastructure、composition 与 shared 的职责，并与已批准的平台/业务物理布局一致。

#### Scenario: 读者查看系统分层和目录导航

- **WHEN** 读者查看系统定位、分层说明和目录结构
- **THEN** 能区分可复用的平台能力、具体业务实现与横向技术层
- **AND** 不会把 Tender 或政策资料验证样本理解为平台一级能力

### Requirement: 总体图必须准确表达入口和组装边界

架构文档 MUST 区分直接 HTTP Application 能力入口与自然语言 Chat 入口。Gateway MUST 被描述为自然语言能力识别、确认和受控分发的控制面，而不是所有 HTTP 接口的必经层。Security MUST 在需要时为入口提供 `RequestPrincipal`；Composition Root MUST 仅被描述为对象组装和固定绑定边界，不得表现为运行时请求中继。

#### Scenario: 读者查看总体运行时路径

- **WHEN** 读者查看总体架构图
- **THEN** 可以识别直接 HTTP 路由到相应 Application Capability 的路径
- **AND** 可以识别 Chat 经 `InteractionChatStreamApplication` 和 Gateway 的自然语言路径
- **AND** 不会将 Composition Root 或 Gateway 误解为所有请求的运行时中转层

### Requirement: 架构文档必须表达受控的 Agent Management 链路

架构文档 MUST 将 Capability Catalog、Agent Call Policy、`AgentCallDispatcher` 与 Agent Runtime 作为 Agent Management 的受控执行结构。自然语言 Agent 调用图 MUST 依次表达 Chat HTTP、`InteractionChatStreamApplication`、Gateway/Capability Catalog、确认策略、`DialogueAgentInvocation`、`AgentCallDispatcher`、Agent Runtime、业务 Agent、`DialogueAgentContinuation` 与 LLM。客户端和模型 MUST NOT 被描述为可直接指定执行目标。

#### Scenario: 读者查看业务 Agent 调用

- **WHEN** 读者查看自然语言请求业务 Agent 的流程图
- **THEN** 可以看到能力目录和策略先于固定分发与运行时执行
- **AND** 可以看到 Tender 仅作为该链路中的业务 Agent 示例
- **AND** 图中不存在客户端或模型直接调用业务 Agent 的路径

### Requirement: 架构文档必须准确表达资料处理、知识检索和业务依赖

架构文档 MUST 将 Ingestion 描述为通用资料处理 Pipeline，并画出其到 Knowledge 写入能力和 LLM Embedding Port 的关系。Knowledge/RAG MUST 是独立的平台能力。`online` MUST 通过 Knowledge Query/RAG 和自身的 `AnswerGenerator` Port 使用检索结果；Tender MUST NOT 被画为依赖 Knowledge/RAG。

#### Scenario: 读者查看资料处理和检索关系

- **WHEN** 读者查看 Ingestion、Knowledge/RAG 与业务应用的图示
- **THEN** 可以看到政策资料仅是 Ingestion 的验证样本，而不是其模块归属
- **AND** 可以看到 Online 经 Knowledge Query/RAG 使用检索能力
- **AND** 图中不存在 `online -> LLM` 或 `Tender -> Knowledge` 的直接依赖边

### Requirement: 架构文档必须采用确认的多轮上下文设计

架构文档 MUST 使用以下多轮上下文链路：Conversation history 经 History Read Service 和 Context Builder 进入 `ChatLlmRequest.history_messages`，再由 LLM 消费。Context Builder MUST 采用连续的近期窗口与成本预算，参数为 `max_messages=20` 与 `max_cost=12_000`；历史角色和顺序 MUST 保留，当前用户输入 MUST 只作为 `user_prompt` 发送一次。文档 MUST NOT 由此引入未确认的 Redis、压缩摘要、长期记忆或持久化记忆设计。

#### Scenario: 读者查看多轮对话上下文

- **WHEN** 读者查看 Conversation 与 Dialogue 的上下文图
- **THEN** 可以追踪历史消息从同一 Conversation 的读取到 LLM 请求装配的过程
- **AND** 可以确认当前用户输入不会同时出现在历史消息和 `user_prompt` 中
- **AND** 不会将未确认的上下文基础设施误解为系统设计的一部分

### Requirement: README 必须提供使用导航而不复制架构设计

README MUST 说明项目背景、系统用途、既有能力、目录导航、环境要求、运行指令和接口访问说明，并链接到 `ARCHITECTURE.md` 获取详细架构。README MUST NOT 复制详细架构图、模块依赖方向或业务流程。没有可确认的部署地址时，接口访问章节 MUST 不虚构地址。

#### Scenario: 使用者从 README 开始了解项目

- **WHEN** 使用者阅读 README
- **THEN** 能找到项目用途、运行前提、启动方式、目录导航和接口访问说明
- **AND** 能通过链接进入完整架构文档
- **AND** 不会在 README 中看到另一套详细架构图或虚构的服务地址
