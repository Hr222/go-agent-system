# 架构演化目标（V2：LLM 对话体系）

> 状态：已完成架构探索，尚未开始实现。
>
> V1 的已实现基线见 [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md)。本文件只描述 V2 的目标架构、演化边界和实施顺序，不把 V2 内容回写为 V1 已实现事实。

## 目标与范围

V2 将 V1 的单轮/MCP 快速入口演化为完整的 LLM 对话体系，首要支持：

- Conversation、历史消息和多轮对话。
- 由 LLM 发起的单个 Tender Agent 调用。
- 显式的意图识别、能力授权和用户确认。
- 为 SubAgent、Workflow、Task Management 和 Harness 保留稳定插口。

V2 当前不实现 SubAgent、Workflow、Task Management 或 Harness。它们不能反向决定首版 Conversation 与 Dialogue 的模型。

## 最终模块归属

以下模块处于同一应用能力层级：

- `LLM`：无状态模型调用、结构化输出和 Provider 适配。
- `Conversation`：会话、消息、Turn、事件、历史持久化和恢复。
- `Dialogue Runtime`：编排一次对话轮次，连接 Conversation、LLM、Gateway 和 Agent Runtime。
- `Interaction Gateway`：统一进行用户请求识别、澄清、能力校验、权限判断和确认策略。
- `Agent Runtime`：执行已授权 Agent Call，并为未来编排提供运行时边界。

`Context Builder` 不属于 LLM 内部，也不是顶级业务模块。它是 Conversation 的应用能力，由 Dialogue Runtime 调用：

```text
Conversation History
  -> Context Policy（选择具备业务意义的历史）
  -> Model Budget Adapter（Token / Provider 限制）
  -> Model Context
  -> Chat Model Port
```

`Structured Agent Call` 是 LLM、Interaction Gateway 和 Agent Runtime 之间的类型化契约，不是新的顶级模块。

## 总体结构

```mermaid
flowchart TB
    User["用户 / 前端"] --> Http["HTTP Interfaces"]
    Http --> DialogueApi["Dialogue API"]
    DialogueApi --> Dialogue["Dialogue Runtime"]

    subgraph Application["应用能力层"]
        LLM["LLM<br/>模型调用能力"]
        Conversation["Conversation<br/>会话与历史消息"]
        ContextBuilder["Conversation Context Builder<br/>历史选择与上下文组装"]
        Gateway["Interaction Gateway<br/>识别 / 澄清 / 授权 / 确认"]
        Catalog["Platform Capability Catalog<br/>平台能力目录"]
        AgentRuntime["Agent Runtime<br/>Agent 执行与未来编排"]
        Knowledge["Knowledge Capability"]
        Ingestion["Ingestion Capability"]
    end

    Dialogue --> Conversation
    Dialogue --> ContextBuilder
    Dialogue --> Gateway
    Dialogue --> LLM
    Conversation --> ContextBuilder
    ContextBuilder --> LLM

    Gateway --> Catalog
    Gateway -. "识别阶段可使用 LLM" .-> LLM
    LLM --> AgentCall["Structured Agent Call<br/>结构化调用契约"]
    AgentCall --> Gateway
    Gateway -->|"授权后的受控分发"| AgentRuntime
    AgentRuntime --> Tender["Tender Agent"]
    AgentRuntime -. "未来插口" .-> SubAgent["SubAgent Group"]
    AgentRuntime -. "未来插口" .-> Workflow["Workflow Runtime"]

    Dialogue --> Knowledge
    Http --> Knowledge
    Http --> Ingestion

    Conversation --> ConversationStore[("Conversation Store<br/>Messages / Events")]
    Gateway --> ProposalStore[("Pending Proposal Store<br/>短 TTL / 一次性消费")]
    Catalog --> CatalogStore[("Capability Catalog Store")]
    LLM --> Providers["LLM Providers"]
    AgentRuntime --> AgentPorts["Agent Capability Ports"]
    Knowledge --> KnowledgeStore[("Knowledge Storage")]
    Ingestion --> KnowledgeStore

    FutureTask["Task Management<br/>未来异步恢复"] -. "未来接入" .-> Dialogue
    FutureHarness["Harness<br/>当前不实现"] -. "未来接入" .-> Dialogue
```

## Gateway 的两个入口

```text
recognize_user_request(user_message, context)
  -> Chat / Agent Candidate / Clarification

authorize_agent_call(structured_agent_call)
  -> Reject / Confirmation Required / Authorized
```

用户自然语言必须先经 Gateway 识别、澄清和确认。模型产生结构化 `Agent Call` 后，Gateway 只做能力、Schema、权限和确认策略校验；不得把该对象再次转换为自然语言重新识别。

## 对话与 Agent 调用链路

```mermaid
sequenceDiagram
    participant U as 用户
    participant H as HTTP API
    participant D as Dialogue Runtime
    participant C as Conversation
    participant X as Context Builder
    participant G as Interaction Gateway
    participant L as LLM
    participant A as Agent Runtime
    participant T as Tender Agent

    U->>H: 发送消息
    H->>D: Start / Continue Turn
    D->>C: 加载会话和历史消息
    C-->>D: Messages / Events
    D->>X: 构建本轮上下文
    X-->>D: Model Context
    D->>G: recognize_user_request(message, context)
    G-->>D: Chat / Agent Candidate / Clarification

    alt 需要澄清或确认
        D->>C: 记录 clarification / approval_required 事件
        D-->>H: 返回澄清或确认请求
    else 可以调用模型
        D->>L: Chat Completion（上下文和能力范围）
        L-->>D: Final Answer 或 Structured Agent Call

        alt Final Answer
            D->>C: 保存 assistant_message
            D-->>H: 返回最终回答
        else Structured Agent Call
            D->>G: authorize_agent_call(typed_call)
            alt Reject
                G-->>D: Reject
                D->>C: 保存 rejected_call 事件
                D-->>H: 返回拒绝或澄清
            else Confirmation Required
                G-->>D: Confirmation Required
                D->>C: 保存 approval_required 事件
                D-->>H: 返回确认请求
            else Authorized
                G-->>D: Authorized
                D->>A: Controlled Dispatch
                A->>T: 执行 Tender Agent
                T-->>A: Agent Result
                A-->>D: Agent Result
                D->>C: 保存 agent_call 与 agent_result
                D->>X: 重新构建包含 Agent Result 的上下文
                D->>L: Continuation Completion
                L-->>D: Final Answer
                D->>C: 保存 assistant_message
                D-->>H: 返回最终回答
            end
        end
    end
```

## 代码层级目标

```text
app/
├── interfaces/http/
│   ├── routes/
│   │   ├── dialogue.py
│   │   ├── conversation.py
│   │   └── interaction.py
│   ├── schemas/
│   └── assemblers/
│
├── modules/
│   ├── llm/
│   │   ├── application/
│   │   ├── ports/
│   │   └── contracts.py
│   ├── conversation/
│   │   ├── domain/
│   │   ├── application/
│   │   └── ports/
│   ├── dialogue/
│   │   ├── domain/
│   │   ├── application/
│   │   └── ports/
│   ├── interaction/
│   │   ├── application/
│   │   └── ports/
│   └── agent/
│       ├── runtime/
│       └── tender/
│
├── infrastructure/
│   ├── llm/
│   ├── interaction/
│   └── persistence/
│       ├── models/
│       └── repositories/
│
└── composition/
    ├── conversation.py
    ├── dialogue.py
    ├── interaction.py
    └── agent.py
```

## 实施顺序

首个 Change 先做 Conversation，建议名称为 `conversation-foundation`。它为 Dialogue Runtime、上下文组装、Agent 结果回填和多轮恢复提供稳定基础。

`conversation-foundation` 包含：

- `Conversation`、`Message`、`Turn`、`ConversationEvent` 领域对象和标识。
- 会话创建、读取、消息追加、历史查询和顺序保证。
- `ConversationRepository`、`MessageRepository` 等持久化 Port 与基础实现。
- `ContextPolicy` 和 `ContextBuilder` 契约；首版只从历史生成有序 `ModelContext`，不调用具体模型。
- `conversation_id`、`turn_id`、`run_id`、`parent_run_id` 等关联标识。
- `approval_required`、`approval`、`agent_call`、`agent_result` 等扩展事件；Proposal 本体仍由 Gateway 的短 TTL 存储负责。

该 Change 不包含 Dialogue Runtime、Interaction Gateway 执行、Agent Runtime 改造、Task Management、Harness 或旧接口删除。

后续顺序固定为：

```text
1. conversation-foundation
2. dialogue-runtime
3. interaction-agent-call-authorization
4. 新对话入口验收后删除 /api/v1/llm/chat
5. SubAgent / Workflow / Task Management / Harness 的独立演化
```

## V1 退场规则

`/api/v1/llm/chat` 是 V1 为快速落地 MCP 链路建立的单轮入口。新 Dialogue API 完成验收后，必须一并删除：

- `app/interfaces/http/routes/llm.py`
- `app/interfaces/http/schemas/llm.py`
- 前端直接调用 `/api/v1/llm/chat` 的逻辑
- 对应的 V1 测试和兼容 Schema

保留并演化的是 `app/modules/llm/`，不是旧 HTTP 入口。
