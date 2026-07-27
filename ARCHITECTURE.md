# 当前架构基准（迭代一）

本版本明确以下长期边界：

- LLM 是独立的通用能力层，不属于任何一个 Agent。
- Agent 是业务能力和编排能力的承载者，通过通用 LLM Port 使用模型。
- Agent Runtime 负责多步骤编排、状态流转和 SubAgent 协作；具体编排框架可以替换。
- Function Calling、MCP 等是 Agent 能力的外部接入协议，不是 LLM 层职责。
- 对话入口不等于 Agent；原始 LLM 对话和 Agent 对话是两种不同的应用用例。
- 上下文记忆属于独立的 Conversation 能力，不应隐含在 LLM Adapter 或具体 Agent 中。
- Conversation 与 Task Management 都是独立的应用能力模块，与 LLM、Agent、Knowledge 和 Ingestion 同级。
- Task Management 负责任务生命周期，不负责模型调用、会话上下文或 Agent 业务编排。

## 总体结构图

```mermaid
flowchart LR
    subgraph Interfaces["Interfaces 外部接口层"]
        direction TB
        Http["HTTP API"]
        HttpAdapter["HTTP Assemblers"]
        AgentAdapter["Agent Protocol Adapters<br/>Function Calling / MCP"]

        Http --> HttpAdapter
    end

    subgraph Applications["Applications 应用模块层"]
        direction TB
        Llm["LLM Capability<br/>Chat / Structured Output / Embedding"]
        Conversation["Conversation Capability<br/>History / Context"]
        Task["Task Management<br/>Lifecycle / Status / Retry"]
        AgentRuntime["Agent Runtime<br/>Orchestration / SubAgents"]
        AgentCapabilities["Agent Capabilities<br/>Tender / Finance / Risk"]
        Online["Online Application<br/>RAG Facade / Decision"]
        Ingestion["Ingestion Application<br/>文档入库用例"]

        HttpAdapter --> Online
        HttpAdapter --> Ingestion
        HttpAdapter --> Llm
        HttpAdapter --> Conversation
        HttpAdapter --> Task
        AgentAdapter --> AgentRuntime
        AgentRuntime --> AgentCapabilities
    end

    subgraph Knowledge["Knowledge 知识能力层"]
        direction TB
        Query["Query Capability<br/>查询 / 检索 / 引用"]
        Write["Write Capability<br/>知识写入"]
        Publish["Publication Service<br/>版本发布 / 激活"]

        Online --> Query
        Ingestion --> Write
        Ingestion --> Publish
    end

    subgraph PortsLayer["Application Ports 应用能力端口"]
        direction TB
        Ports["Business Ports<br/>Read / Write / Publication"]
        LlmPorts["LLM Ports<br/>Chat / Structured / Embedding"]
        ConversationPorts["Conversation Ports<br/>Messages / Context / Persistence"]
        TaskPorts["Task Ports<br/>Lifecycle / Status / Retry"]
    end

    subgraph Persistence["Persistence 持久化与基础设施层"]
        direction TB
        Repositories["Repository Layer<br/>Read / Write / Publication Repository"]
        Providers["Technical Adapters<br/>GLM / LangChain / OCR / File System"]
        Storage[("PostgreSQL / pgvector<br/>Published Read Model / Vector Index")]

        Query --> Ports
        Write --> Ports
        Publish --> Ports
        Llm --> LlmPorts
        Conversation --> ConversationPorts
        Task --> TaskPorts
        AgentRuntime --> LlmPorts
        AgentCapabilities --> LlmPorts
        Ports -.实现.-> Repositories
        LlmPorts -.实现.-> Providers
        ConversationPorts -.实现.-> Repositories
        TaskPorts -.实现.-> Repositories
        Repositories --> Storage
    end

    Composition["Composition Root<br/>ApplicationContainer"]

    Composition -.->|组装| Llm
    Composition -.->|组装| Conversation
    Composition -.->|组装| Task
    Composition -.->|组装| AgentRuntime
    Composition -.->|组装| Online
    Composition -.->|组装| Ingestion
    Composition -.->|组装| Query
    Composition -.->|组装| Repositories
    Composition -.->|组装| Providers

    classDef interface fill:#e8f1ff,stroke:#3478c9,color:#123b63;
    classDef application fill:#eaf7ee,stroke:#3c9b5f,color:#1d5c32;
    classDef knowledge fill:#fff7e6,stroke:#d99a18,color:#714e00;
    classDef port fill:#eef7f7,stroke:#3b8f8f,color:#1f5d5d;
    classDef infrastructure fill:#f4f0ff,stroke:#7956b3,color:#432d6e;
    classDef composition fill:#f5f5f5,stroke:#666,color:#333;

    class Http,HttpAdapter,AgentAdapter interface;
    class Llm,Conversation,Task,AgentRuntime,Online,Ingestion application;
    class Query,Write,Publish knowledge;
    class Ports,LlmPorts,ConversationPorts,TaskPorts port;
    class Repositories,Providers,Storage infrastructure;
    class Composition composition;
```

## 模块组织基线

```text
app/
├── modules/                              # 应用能力模块总包
│   ├── llm/                               # 独立 LLM 能力层
│   │   ├── application/
│   │   │   └── chat.py                    # Chat / 模型调用用例
│   │   ├── ports/
│   │   │   ├── chat_port.py               # 文本对话能力
│   │   │   ├── structured_output_port.py  # 结构化输出能力
│   │   │   └── embedding_port.py          # 向量能力边界
│   │   └── contracts.py                   # LLM 请求、结果和失败契约
│   │
│   ├── conversation/                      # 会话、上下文和消息生命周期
│   │   ├── application/
│   │   ├── domain/
│   │   └── ports/
│   │
│   ├── task/                              # 任务生命周期、状态和重试
│   │   ├── application/
│   │   ├── domain/
│   │   └── ports/
│   │
│   ├── agent/                             # Agent 业务能力与运行时
│   │   ├── runtime/                        # 编排、状态和 SubAgent 协作边界
│   │   ├── tender/
│   │   │   ├── application/
│   │   │   ├── domain/
│   │   │   └── ports/
│   │   └── ...
│   │
│   ├── online/                           # 在线 RAG / Decision
│   │   ├── application/
│   │   │   ├── rag_facade.py
│   │   │   ├── ask_knowledge.py
│   │   │   └── policy_decision.py
│   │   ├── domain/
│   │   │   ├── checklist/
│   │   │   │   ├── definitions.py
│   │   │   │   └── registry.py
│   │   │   └── decision_result.py
│   │   └── contracts.py
│   │
│   ├── knowledge/                        # 知识能力层
│   │   ├── application/
│   │   │   ├── query_capability.py
│   │   │   ├── publication_service.py
│   │   │   └── write_capability.py
│   │   ├── domain/
│   │   │   ├── knowledge_version.py
│   │   │   └── publication_state.py
│   │   ├── ports/                         # 仓储抽象与能力端口
│   │   │   ├── read_port.py
│   │   │   ├── write_port.py
│   │   │   └── publication_port.py
│   │   └── retrieval/
│   │       ├── pipeline.py
│   │       ├── policies.py
│   │       ├── rerank.py
│   │       └── vector_search.py
│   │
│   └── ingestion/                        # 独立文档入库层
│       ├── application/
│       │   ├── ingestion_use_case.py
│       │   └── scan_candidates.py
│       ├── domain/
│       │   └── policies.py
│       ├── ports/
│       │   ├── file_port.py
│       │   ├── embedding_port.py
│       │   └── ocr_port.py
│       └── pipeline/
│           ├── pipeline.py
│           ├── context.py
│           ├── persistence.py
│           └── steps/
│
├── interfaces/                           # 外部接口层
│   ├── http/                             # 给前端的 HTTP API
│   │   ├── routes/
│   │   ├── assemblers/
│   │   └── schemas/
│   └── agent/                             # Agent 外部接入适配层
│       ├── function_calling_adapter.py
│       ├── mcp_adapter.py
│       └── contracts.py
│
├── infrastructure/                       # 基础设施具体实现
│   ├── persistence/
│   │   ├── repositories/                  # 仓储层具体实现
│   │   │   ├── knowledge_read_repository.py
│   │   │   ├── knowledge_write_repository.py
│   │   │   └── knowledge_publication_repository.py
│   │   ├── models/                        # ORM 持久化模型
│   │   └── session.py
│   ├── llm/
│   │   ├── openai_client_factory.py
│   │   ├── langchain_glm_adapter.py
│   │   ├── chat_adapter.py
│   │   ├── llm_client.py
│   │   └── embedding_client.py
│   ├── agent/
│   │   └── langgraph_runtime_adapter.py
│   ├── ocr/
│   │   └── tencent_ocr.py
│   └── filesystem/
│       ├── policy_file_service.py
│       └── upload_service.py
│
├── composition/                          # Composition Root
│   ├── root.py
│   ├── llm.py
│   ├── agent.py
│   ├── conversation.py
│   ├── task.py
│   ├── online.py
│   ├── knowledge.py
│   └── ingestion.py
│
└── shared/                               # 少量公共基础类型
    ├── exceptions.py
    ├── identifiers.py
    └── events.py
```

## 关键边界图

```mermaid
flowchart TB
    HTTP["interfaces/http"]
    AgentProtocols["interfaces/agent<br/>Function Calling / MCP"]
    LlmApplication["modules/llm/application"]
    LlmPorts["modules/llm/ports"]
    Conversation["modules/conversation"]
    ConversationPorts["modules/conversation/ports"]
    TaskManagement["modules/task"]
    TaskPorts["modules/task/ports"]
    AgentRuntime["modules/agent/runtime"]
    AgentCapabilities["modules/agent/*"]
    Online["modules/online"]
    Ingestion["modules/ingestion"]
    KnowledgeQuery["modules/knowledge<br/>Query Capability"]
    KnowledgeWrite["modules/knowledge<br/>Write / Publication Capability"]
    Ports["modules/knowledge/ports"]
    Repositories["infrastructure/persistence/repositories"]
    LlmAdapters["infrastructure/llm"]
    Providers["infrastructure/ocr / filesystem"]
    Storage[("PostgreSQL / pgvector / Object Storage")]

    HTTP --> LlmApplication
    HTTP --> Conversation
    HTTP --> TaskManagement
    HTTP --> AgentRuntime
    HTTP --> Online
    HTTP --> Ingestion
    AgentProtocols --> AgentRuntime

    LlmApplication --> LlmPorts
    Conversation --> ConversationPorts
    TaskManagement --> TaskPorts
    AgentRuntime --> LlmPorts
    AgentRuntime --> AgentCapabilities
    AgentCapabilities --> LlmPorts
    AgentCapabilities --> KnowledgeQuery
    Online --> KnowledgeQuery
    Ingestion --> KnowledgeWrite
    KnowledgeQuery --> Ports
    KnowledgeWrite --> Ports
    Ports -.实现.-> Repositories
    ConversationPorts -.实现.-> Repositories
    TaskPorts -.实现.-> Repositories
    LlmPorts -.实现.-> LlmAdapters
    Repositories --> Storage
    Ingestion -.依赖端口.-> Providers

    Forbidden["禁止：业务模块直接依赖 SDK / DB<br/>禁止：Agent 绕过 Application 访问 Repository<br/>禁止：Domain 依赖 HTTP / LangChain / LangGraph"]

    classDef forbidden fill:#fff1f0,stroke:#cf1322,color:#820014;
    class Forbidden forbidden;
```

## 核心调用关系图

```mermaid
flowchart LR
    subgraph External["外部调用"]
        HTTP["HTTP API"]
        FunctionCalling["Function Calling"]
        MCP["MCP Client / Server"]
        Source["文档 / PDF / 图片"]
    end

    subgraph Llm["独立 LLM 能力层"]
        Chat["Chat Application"]
        LlmPort["Chat / Structured LLM Port"]
        LlmAdapter["GLM / LangChain Adapter"]
    end

    subgraph ConversationCapability["Conversation 能力层"]
        ConversationApplication["Conversation Application"]
        ConversationPort["Message / Context Port"]
        ConversationRepository["Conversation Repository"]
    end

    subgraph TaskCapability["Task Management 能力层"]
        TaskApplication["Task Application"]
        TaskPort["Task Lifecycle Port"]
        TaskRepository["Task Repository"]
    end

    subgraph Agent["Agent 应用与运行时"]
        AgentHttp["Agent HTTP Adapter"]
        AgentProtocol["Function / MCP Adapter"]
        Runtime["Agent Runtime<br/>Orchestration / SubAgents"]
        Registry["Agent Capability Registry"]
        Tender["Tender Agent"]
        OtherAgents["Finance / Risk / Other Agents"]
    end

    subgraph Online["在线应用层：RAG / Decision"]
        HttpAdapter["HTTP Assembler"]
        Facade["RAG Application Facade"]
        Ask["AskKnowledge"]
        Decision["Policy Decision"]
    end

    subgraph Knowledge["知识能力层"]
        Query["KnowledgeBaseQueryCapability"]
        Read["KnowledgeBaseReadPort"]
        ReadRepo["KnowledgeReadRepository"]
        Write["KnowledgeBaseWritePort"]
        WriteRepo["KnowledgeWriteRepository"]
        Publish["KnowledgePublicationService"]
        PublishRepo["KnowledgePublicationRepository"]
        Store[("Knowledge Base<br/>Published Read Model / Vector Index")]
    end

    subgraph Ingestion["独立入库应用层"]
        IngestAdapter["Ingestion Adapter"]
        Ingest["Ingestion Use Case"]
        Pipeline["解析 / OCR / 清洗<br/>分节 / 切块 / 向量化"]
    end

    PublicationHttp["HTTP Publication Route"]

    HTTP --> Chat
    HTTP --> ConversationApplication
    HTTP --> TaskApplication
    HTTP --> AgentHttp
    HTTP --> HttpAdapter
    HTTP --> PublicationHttp
    FunctionCalling --> AgentProtocol
    MCP --> AgentProtocol

    Chat --> LlmPort
    ConversationApplication --> ConversationPort
    ConversationPort --> ConversationRepository
    TaskApplication --> TaskPort
    TaskPort --> TaskRepository
    AgentHttp --> Runtime
    AgentProtocol --> Runtime
    Runtime --> LlmPort
    Runtime --> Registry
    Registry --> Tender
    Registry --> OtherAgents
    Tender --> LlmPort
    HttpAdapter --> Facade
    Facade --> Ask
    Facade --> Decision

    Ask --> Query
    Decision --> Query
    Query --> Read
    Read --> ReadRepo
    ReadRepo --> Store

    Source --> IngestAdapter
    IngestAdapter --> Ingest
    Ingest --> Pipeline
    Pipeline --> Write
    Write --> WriteRepo
    PublicationHttp --> Publish
    Publish --> PublishRepo
    PublishRepo --> Store
    LlmPort --> LlmAdapter
```

## LLM、Agent 与协议边界

### LLM 能力层

`modules/llm` 表达模型调用能力，不表达任何具体业务。它可以被普通 Chat、Agent Runtime、RAG 或其他应用能力共同使用。

LLM 层负责的能力包括：

- 文本对话和模型响应
- Structured Output 和 Schema 校验
- Embedding 等模型能力
- Provider 配置、超时、重试边界和错误契约
- Prompt 输入的技术载体和模型调用结果

LLM 层不负责：

- 招标书、财务或风控业务规则
- Agent 状态机和多 Agent 协作
- Function Calling 工具注册与业务执行
- MCP 会话和远程能力治理
- 会话历史和上下文持久化

`infrastructure/llm` 只实现 LLM Port，具体 SDK、LangChain Chat Model 和 Provider Client 不得向上层泄漏。

### Agent 能力层

`modules/agent/*` 负责具体业务 Agent 和可组合能力。每个 Agent 可以使用 LLM，也可以调用知识库、文件、外部服务或其他 Agent，但不重复实现 LLM Chat。

Agent 可以通过稳定的能力契约被运行时发现和调用。能力契约至少包含：

- 能力名称和描述
- 输入 Schema
- 输出 Schema
- 执行状态和错误契约
- 权限、超时和可重试边界

一个 Agent 不等于一个 Chat 服务，也不要求每个 Agent 都暴露自己的对话接口。是否以对话方式使用 Agent，由上层交互用例和 Agent Runtime 决定。

### Agent Runtime 与 SubAgent

Agent Runtime 负责：

- 选择和调用 Agent 能力
- 管理多步骤执行状态
- 将 LLM 返回的工具调用转换为能力调用
- 协调多个 Agent 或 SubAgent
- 处理暂停、失败、重试和恢复边界

LangGraph 可以作为 Agent Runtime 的一种具体实现，但不能成为 Domain 或通用 LLM Port 的依赖。后续更换编排实现时，Agent 业务能力和 LLM Port 不应跟着改变。

### Function Calling 与 MCP

Function Calling 和 MCP 都属于 Agent 能力的接入协议，分别适配不同的调用来源或外部生态：

```text
LLM 返回工具调用
  -> Function Calling Adapter
  -> Agent Capability / Application Use Case

MCP 请求或响应
  -> MCP Adapter
  -> Agent Capability / Application Use Case
```

两者最终都应落到稳定的 Agent Capability 或 Application Use Case，不能直接操作 Repository、数据库或具体模型客户端。协议适配器不应把 Function Calling 或 MCP 的协议对象泄漏到 Domain。

### Conversation 与上下文

会话管理是独立的 Conversation 能力。它负责会话 ID、消息历史、上下文裁剪、持久化和恢复；LLM Adapter 只接收本次调用所需的消息或 Prompt，不自行保存上下文。Agent Runtime 也不应隐式承担长期会话存储。

Conversation 可以为普通 Chat 或 Agent 交互提供上下文，但是否启用上下文由具体应用用例决定。当前 `modules/llm` 的单轮 Chat 不创建会话、不读取历史，也不依赖 Conversation 模块。

### Task Management 与任务生命周期

Task Management 是与 Conversation 同级的独立能力模块。它负责任务 ID、任务状态、状态转换、失败、重试、幂等和持久化；它不负责 LLM 调用、会话历史、上下文组装或 Agent 业务编排。

Tender Agent 如果未来需要异步处理，可以通过明确的 Task Application / Port 使用任务能力，但不能把任务状态查询直接塞入 `modules/llm` 或某个 Agent 内部。Task Management 是否参与某个 Agent 用例，应由上层 Application 通过契约决定。

当前 `complete-llm-chat-acceptance` Change 不包含 Conversation 或 Task Management。后续这两类能力必须分别建立独立的 OpenSpec Change 和验收契约。

## HTTP 交互契约与适配边界

HTTP 接口不仅是能力的暴露入口，也是前端与应用层之间的交互契约。此前架构图已经定义了 HTTP Route、Assembler、Application 和 Port 的调用关系，但没有明确 Request Body、Query、Path Parameter 与 Response Body 的归属。本节补充这一部分。

### HTTP 交互链条

```text
前端
  -> HTTP Request
  -> interfaces/http/routes
  -> interfaces/http/schemas
  -> interfaces/http/assemblers
  -> Application Command / Query
  -> Capability / Use Case
  -> Port
  -> Repository / Provider

Repository / Provider
  -> Application Result
  -> interfaces/http/assemblers
  -> interfaces/http/schemas
  -> HTTP Response
  -> 前端
```

HTTP 层负责协议适配，不负责业务编排。Application 层负责用例编排，不依赖 FastAPI、`Request`、`Response`、`UploadFile` 或 HTTP Schema。Domain 层不依赖 HTTP、数据库、Repository 或具体基础设施实现。

### 对象归属规则

| 对象 | 所属位置 | 职责 | 约束 |
|---|---|---|---|
| Request Body | `app/interfaces/http/schemas/` | 定义 JSON / multipart 请求结构和边界校验 | 不直接传入 Application |
| Query / Path 参数 | `app/interfaces/http/schemas/` 或 Route 参数 | 定义分页、筛选、资源 ID 等 HTTP 输入 | 复杂查询应定义独立 Schema |
| Response Body | `app/interfaces/http/schemas/` | 定义返回给前端的协议结构 | 不直接使用 ORM Model 或 Domain Entity |
| HTTP Assembler | `app/interfaces/http/assemblers/` | Request Schema 与 Application Command/Query 互转；Application Result 与 Response Schema 互转 | 不实现业务规则 |
| Application Command / Query | `app/modules/*/application/` | 描述一个用例的内部输入 | 不依赖 HTTP 层类型 |
| Application Result | `app/modules/*/application/` | 描述一个用例的内部输出 | 可以作为 HTTP、Agent 等多个适配器的输入 |
| Capability / Use Case | `app/modules/*/application/` | 编排业务流程并调用 Port | 不直接访问数据库或 HTTP |
| Port | `app/modules/*/ports/` | 定义应用层所需的读写能力 | 由 Infrastructure 实现 |
| Domain Entity / Value Object | `app/modules/*/domain/` | 承载领域状态和业务不变量 | 不添加页面展示字段 |

同一个业务结果如果同时被 HTTP 和 Agent 使用，应共享 Application Result，但分别建立 HTTP Assembler 和 Agent Adapter；不能让 Agent 或前端直接复用对方的协议 Schema。

### 知识库管理交互的推荐结构

知识库管理页面属于 HTTP 应用交互，不等同于底层知识检索能力。管理页面需要的统计、文档列表和文档详情属于管理读模型，应通过 Application Query 和 Read Port 提供。

```text
app/interfaces/http/
├── routes/
│   ├── knowledge_management.py
│   └── ingestion_retry.py
├── schemas/
│   ├── knowledge_management.py
│   └── ingestion_retry.py
└── assemblers/
    ├── knowledge_management.py
    └── ingestion_retry.py

app/modules/knowledge/application/
├── management_contracts.py
└── management_service.py

app/modules/knowledge/ports/
└── management_read_port.py

app/modules/ingestion/application/
└── retry_ingestion.py
```

推荐的边界如下：

```text
KnowledgeDocumentListRequest
  -> ListKnowledgeDocumentsQuery
  -> KnowledgeManagementService
  -> ManagementReadPort
  -> KnowledgeReadRepository
  -> KnowledgeDocumentListResult
  -> KnowledgeDocumentListResponse
```

`KnowledgeDocumentListResponse` 可以包含 `file_name`、`file_size`、`processing_status`、`processing_progress`、`chunk_count`、`updated_at` 和 `error_message` 等前端字段；这些字段属于 HTTP Read Model，不应直接加入 Domain Entity。

### 上传、入库与发布交互

上传交互由多个 HTTP 用例组成，不应把一次上传请求伪装成一个同步的“文档创建”接口：

```text
POST /api/v1/kb/policy-pipeline/preview-upload
  -> PolicyUploadPreviewRequest / multipart boundary
  -> IngestionUseCase.preview()
  -> PolicyUploadPreviewResponse

用户确认
  -> PolicyUploadIngestRequest
  -> POST /api/v1/kb/policy-pipeline/ingest-upload
  -> IngestionUseCase.ingest()
  -> PolicyPipelineResponse

入库成功
  -> KnowledgePublicationRequest
  -> POST /api/v1/kb/publication/activate
  -> KnowledgePublicationService.publish()
  -> KnowledgePublicationResponse
```

文件流、`UploadFile` 和临时上传 ID 只停留在 HTTP / Upload Adapter 边界；Application 只接收已经转换后的上传命令或可解析的文件引用。

### 检索交互

检索和问答接口复用已有 Knowledge Query Capability，不因前端工作台增加新的检索算法入口：

```text
RetrievalSearchRequest
  -> KnowledgeQuery
  -> KnowledgeBaseQueryCapability
  -> KnowledgeQueryResult
  -> RetrievalSearchResponse
```

HTTP 响应中的 `hits`、`citations` 和 `debug` 是接口展示契约；检索内部的召回、融合、rerank 和追踪对象仍属于 `modules/knowledge/retrieval`，不得由前端或 HTTP Route 直接拼装。

### 当前接口补充原则

1. 已有能力优先复用：检索、问答、上传预览、正式入库、版本发布继续使用现有 Application Capability。
2. 缺失内容优先补 HTTP Schema、Assembler、Route 和必要的 Application Query/Command，不重写底层算法。
3. 管理概览、文档列表、文档详情属于新的 Application Read Model，不修改为 Domain 对象。
4. 现有 `/api/v1/kb/documents` 是制度下拉列表契约；正式管理列表应新增独立的管理响应契约，避免破坏已有调用方。
5. 文档重试属于 `modules/ingestion/application` 的入库用例，HTTP 路由只是外部适配入口，不将重试逻辑放入 `modules/knowledge/domain`。

## Checklist 与 RAG 的架构对应

Checklist 场景属于 `modules/online/domain/checklist`，负责场景定义、规则要求和输入材料核验；它不直接实现 RAG，也不直接访问数据库或具体 Repository。

Checklist 通过 `modules/online/application/rule_retrieval` 调用 Knowledge Query Capability，使用 `modules/knowledge/retrieval` 提供的召回、融合、rerank 和来源追踪能力，得到规则证据包后再进行领域判断。

具体场景的新增方式和各层职责见 `docs/Checklist场景与RAG检索扩展说明.md`。
