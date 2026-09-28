# 低代码 Agent 平台 V1 学习清单

> 目标：围绕当前 Go Agent System，系统学习如何构建一个允许用户自行创建 Agent、配置工具和知识库、编排 Workflow，并运行多 Agent 协作流程的低代码 Agent 平台。
>
> 本文档是学习路线和自检清单，不是产品规格，也不代表文档中出现的能力已经在当前项目实现。凡是涉及当前代码的地方，以代码、`ARCHITECTURE.md`、OpenSpec 和系统看板为准。

## 配套正文

本文件负责总索引、学习顺序和自检；可以直接把下面的正文当作知识储备材料阅读：

1. [LLM 与 Prompt、上下文工程学习笔记](LLM与Prompt上下文工程学习笔记.md)：模型、消息、Prompt、上下文窗口、Token、结构化输出和流式调用。
2. [Agent 与 Tool Calling 学习笔记](Agent与Tool%20Calling学习笔记.md)：Agent 组成、执行循环、能力目录、工具授权、错误和安全边界。
3. [LangChain 与 LangGraph 学习笔记](LangChain与LangGraph学习笔记.md)：框架对象、状态图、Checkpoint、适配边界和当前项目的真实接入情况。
4. [Workflow 与运行时学习笔记](Workflow与运行时学习笔记.md)：Definition、Version、DAG、Node Run、调度、重试、取消和恢复。
5. [多 Agent 协作学习笔记](多%20Agent%20协作学习笔记.md)：Pipeline、Parallel、Fan-in、Supervisor、Handoff、Review 和上下文传递。
6. [Agent 平台数据模型与 Runtime 学习笔记](Agent平台数据模型与Runtime学习笔记.md)：平台对象、发布生命周期、动态编译、运行事实和一致性。
7. [低代码平台 Builder、安全与评测学习笔记](低代码平台Builder安全与评测学习笔记.md)：Agent Builder、Workflow Builder、权限、安全、观测和质量评测。

已有的 [RAG学习笔记](../RAG学习笔记.md)、[上下文管理与多轮对话学习笔记](../上下文管理与多轮对话学习笔记.md) 和 [Task Management学习笔记](../Task%20Management学习笔记.md) 继续作为专题材料使用。

---

## 一、先建立总认识

### 1.1 项目最终要解决什么问题

目标不是只做一个 Tender Agent，也不是只做一个聊天机器人，而是提供一套平台，让用户可以完成下面的闭环：

```text
创建 Agent
  -> 配置 Prompt、模型、知识库和工具
  -> 测试 Agent
  -> 发布 Agent 版本

创建 Workflow
  -> 添加 Agent、Tool、条件和汇总节点
  -> 配置节点输入输出
  -> 连接节点
  -> 测试运行
  -> 发布 Workflow 版本

运行 Workflow
  -> 创建一次运行
  -> 调度多个节点
  -> 执行多个 Agent 协作
  -> 保存事件、中间结果和最终结果
  -> 在前端查看过程和结果
```

### 1.2 八个核心概念的关系

```text
LLM
  提供语言理解和生成能力
  |
  v
Agent
  用 Prompt、模型、工具、知识和状态完成一个职责
  |
  +--> Tool / Knowledge / Memory
  |
  v
Workflow
  定义多个节点之间的依赖、分支、并行和数据传递
  |
  v
Multi-Agent Collaboration
  多个 Agent 按 Pipeline、Parallel、Supervisor 或 Handoff 协作
  |
  v
Runtime
  按已发布定义真正执行、重试、取消、恢复和记录
  |
  v
Low-code Platform
  让用户通过界面完成定义、测试、发布和运行
```

### 1.3 最容易混淆的三件事

| 概念 | 解决的问题 | 例子 |
| --- | --- | --- |
| Agent | 一个智能执行单元如何完成职责 | 招标需求分析 Agent |
| Workflow | 多个步骤如何连接和执行 | 先分析，再检索，再审核 |
| Multi-Agent | 多个 Agent 如何分工协作 | 分析 Agent 把结构化结果交给生成 Agent |

Workflow 不等于多 Agent。Workflow 可以编排普通工具，也可以编排 Agent。多 Agent 协作通常需要 Workflow 作为显式的协作骨架，但也可以通过 Supervisor 或 Handoff 动态决定下一个 Agent。

V1 建议先采用可控的形式：

```text
Workflow
  -> Agent 节点
  -> Tool 节点
  -> 条件节点
  -> 汇总节点
```

暂时不要把所有协作都交给一个自由运行的 Supervisor。自由度越高，越难调试、计费、审计、重试和复现。

---

## 二、如何使用这份清单

### 2.1 标记规则

- `[ ]`：尚未学习或尚未验证。
- `[-]`：正在学习，能够复述一部分但还不能独立设计。
- `[x]`：已经理解，并完成了对应练习或代码验证。
- `当前已有`：代码中已经存在相关基础能力，但不等于已经满足低代码平台 V1。
- `需要补齐`：为了平台目标还需要学习、设计或实现的内容。

### 2.2 每个主题都要留下四类结果

学习每个主题时，不要只看概念。至少留下：

1. 用自己的话写出的定义。
2. 一张结构图或时序图。
3. 一个与当前项目对应的代码定位。
4. 一个可以验收的练习结果。

### 2.3 推荐记录模板

```text
主题：

我的理解：

它解决的问题：

它不负责的问题：

当前项目对应代码：

一个最小示例：

失败场景：

我还没有理解的地方：

完成证据：
```

---

## 三、当前项目基线：先知道已经有什么

这一部分不是学习新概念，而是避免把项目已有内容重复当成空白，也避免把固定代码误认为已经是低代码平台。

### 3.1 当前已经具备的平台外围

- `[x]` LLM Chat、流式 Chat、Structured Output、Embedding。
- `[x]` OpenAI-compatible Provider、DeepSeek 和 GLM 适配。
- `[x]` 请求超时、限流、并发治理、错误分类和重试基础。
- `[x]` Conversation 创建、历史消息、上下文窗口、消息持久化。
- `[x]` Dialogue 与 Interaction Gateway。
- `[x]` Capability Catalog、权限检查、确认提议和受控分发。
- `[x]` Agent Runtime 和固定分发策略。
- `[x]` 附件上传、访问绑定、读取和下载资源。
- `[x]` Ingestion Pipeline、解析、清洗、分块、Embedding 和 Knowledge 写入。
- `[x]` PostgreSQL + pgvector、知识库发布、检索、引用和证据不足处理。
- `[x]` Task、Attempt、Event、Worker、lease、重试、取消和恢复。
- `[x]` Workflow Run、Node Run、DAG 校验、幂等、取消、失败和重试的后端契约。
- `[x]` Tender 作为业务 Agent 和平台能力样本。

### 3.2 当前还不能直接等同于低代码平台的部分

- `[ ]` 用户可持久化创建 Agent Definition。
- `[ ]` Agent 草稿、发布版本和版本回滚。
- `[ ]` 用户可选择模型、Prompt、工具、知识库和输入输出 Schema。
- `[ ]` 用户可创建和保存 Workflow Definition。
- `[ ]` 用户可通过前端编辑节点和连线。
- `[ ]` Workflow 动态加载用户定义，而不是只加载 Composition 中固定注册的版本。
- `[ ]` Agent 节点之间的显式输入输出映射。
- `[ ]` 多 Agent Pipeline、Parallel、Fan-in 等运行时协作。
- `[ ]` Workflow 公开 HTTP API、编辑器 API 和调试运行 API。
- `[ ]` Workflow 运行进度、节点日志、中间结果和最终结果的完整展示。
- `[ ]` 用户自定义工具的安全注册、凭据管理和权限边界。

### 3.3 当前代码阅读入口

按这个顺序阅读，边读边在本清单中补充自己的理解：

1. `app/platform/llm/`
2. `app/infrastructure/llm/`
3. `app/platform/interaction/domain/capability.py`
4. `app/platform/interaction/application/catalog.py`
5. `app/platform/interaction/application/agent_dispatch.py`
6. `app/platform/agent/`
7. `app/platform/conversation/`
8. `app/platform/dialogue/`
9. `app/platform/task/`
10. `app/platform/workflow/domain/`
11. `app/platform/workflow/application/`
12. `app/platform/workflow/ports/`
13. `app/composition/workflow.py`
14. `app/business/agents/tender/`
15. `frontend/src/features/mock-workspace/pages/MockWorkspacePage.tsx`
16. `frontend/src/app/router.tsx`

### 3.4 当前 Workflow 的事实判断

当前 Workflow 基础模型已经存在，但目前主要是固定版本和固定能力绑定：

```text
Composition Root
  -> 注册 tender-generation:v1
  -> Workflow 节点绑定 tender.generate_bid_skeleton
  -> Workflow Runtime 执行固定能力
```

这说明：

- Workflow 可以把能力组织成有依赖关系的执行流程。
- 能力目录已经为 Agent 和非 Agent 能力提供统一入口。
- 当前节点类型主要是 `capability`。
- 当前并没有用户创建 Definition、发布版本和动态编排产品。
- 当前也没有真正实现多个 Agent 节点的协同闭环。

---

## 四、阶段一：LLM 基础

### 4.1 学习目标

理解 LLM 在平台中的职责边界：它负责根据输入生成输出，但不天然负责会话、权限、工具执行、任务状态、Workflow 或业务事实。

### 4.2 概念清单

- `[ ]` Token、上下文窗口和输入输出长度。
- `[ ]` System Prompt、Developer Prompt、User Prompt、Assistant Message。
- `[ ]` Chat Completion 与普通文本生成的区别。
- `[ ]` Temperature、Top P、最大输出 Token 等生成参数。
- `[ ]` 流式输出和非流式输出的区别。
- `[ ]` Structured Output 与普通文本输出的区别。
- `[ ]` JSON Schema 对模型输出的约束作用。
- `[ ]` 模型不具备天然事实记忆的原因。
- `[ ]` 模型幻觉、拒答和不确定性。
- `[ ]` Provider、模型名、凭据和运行配置的关系。
- `[ ]` 请求超时、限流、重试和错误分类。
- `[ ]` 模型调用成本和 Token 预算。

### 4.3 必须理解的边界

```text
LLM 负责：
  理解文本、生成文本、输出结构化结果、提出工具调用意图

LLM 不负责：
  证明事实真实、决定权限、直接访问数据库、保证副作用幂等、保存任务状态
```

### 4.4 与当前项目对应的位置

- `app/platform/llm/`：平台 LLM 契约和应用能力。
- `app/infrastructure/llm/`：Provider 和 LangChain 适配。
- `app/composition/llm.py`：模型对象组装和 Provider 选择。
- `app/infrastructure/llm/openai_compatible_chat_adapter.py`：消息转换和 Chat 调用。
- `app/infrastructure/llm/openai_compatible_structured_adapter.py`：结构化输出。

### 4.5 练习

- `[ ]` 用自己的话解释“模型输出 JSON”为什么不等于“系统已经得到可信数据”。
- `[ ]` 画出一次流式 Chat 从 HTTP 到 Provider 的调用链。
- `[ ]` 列出至少五种模型调用失败，并判断哪些适合重试。
- `[ ]` 说明为什么模型调用期间不应长期占用数据库连接。
- `[ ]` 给一个 Agent 调用设计最大 Token、超时和重试策略。

### 4.6 阶段验收

能够回答：

1. 为什么 Conversation 不能由 LLM 自己保存？
2. 为什么 Structured Output 仍然需要服务端校验？
3. 为什么失败重试不能简单地对所有异常都执行？
4. 为什么平台需要把 Provider SDK 隔离在 Infrastructure？

---

## 五、阶段二：Agent 基础

### 5.1 Agent 的最小定义

Agent 不是“换了一个名字的 Chat”。一个实用的 Agent 至少包含：

```text
Agent
  = Model
  + System Prompt
  + Input Contract
  + Output Contract
  + Tool Set
  + Knowledge Sources
  + Memory / Context Policy
  + Permission Policy
  + Execution Policy
```

### 5.2 概念清单

- `[ ]` Chat、Chain、Agent 的区别。
- `[ ]` Agent 的角色、职责和边界。
- `[ ]` Agent 输入、上下文、工作记忆和输出。
- `[ ]` Agent 执行循环：思考、选择工具、调用工具、读取结果、继续或结束。
- `[ ]` Tool Calling 的基本过程。
- `[ ]` Agent 如何知道可用工具。
- `[ ]` Agent 如何判断应该调用工具还是直接回答。
- `[ ]` Agent 如何处理工具失败。
- `[ ]` Agent 如何处理证据不足。
- `[ ]` Agent 如何输出结构化结果。
- `[ ]` Agent 的最大轮次和最大工具调用次数。
- `[ ]` Agent 的超时、取消和预算边界。
- `[ ]` Agent 与 Conversation 的关系。
- `[ ]` Agent 与 Task 的关系。
- `[ ]` Agent 与 Workflow 节点的关系。

### 5.3 普通 Chat 与 Agent 的对比

```text
普通 Chat：
  用户输入 -> 模型 -> 文本回答

Agent：
  用户输入
    -> 模型判断当前任务
    -> 选择工具或知识源
    -> 调用工具
    -> 读取工具结果
    -> 必要时继续调用
    -> 生成结构化或自然语言结果
```

### 5.4 Agent Definition 学习清单

未来用户自定义 Agent 时，至少要理解以下字段为什么存在：

- `[ ]` `agent_id`：稳定身份，不随版本变化。
- `[ ]` `name`：用户看到的名称。
- `[ ]` `description`：用于展示和候选发现。
- `[ ]` `system_prompt`：职责和行为规则。
- `[ ]` `model_config`：模型、参数和 Token 限制。
- `[ ]` `input_schema`：接受什么输入。
- `[ ]` `output_schema`：输出什么结果。
- `[ ]` `tool_bindings`：允许调用哪些工具。
- `[ ]` `knowledge_bindings`：允许查询哪些知识库。
- `[ ]` `memory_policy`：允许读取哪些会话或上下文。
- `[ ]` `permission_policy`：谁可以使用。
- `[ ]` `timeout_policy`：多久超时。
- `[ ]` `retry_policy`：哪些失败可以重试。
- `[ ]` `status`：草稿、已发布、已下线等生命周期。
- `[ ]` `version`：运行时绑定的不可变版本。

### 5.5 练习：设计一个非 Tender Agent

设计一个“制度问答 Agent”，写出：

- Agent 名称和职责。
- 它可以回答什么。
- 它明确不能回答什么。
- 它绑定哪个知识库。
- 它是否允许调用外部工具。
- 输入 Schema。
- 输出 Schema。
- 证据不足时如何返回。
- 权限不足时如何返回。
- 模型调用超时和重试策略。

### 5.6 阶段验收

能够回答：

1. 一个 Agent 为什么必须有权限边界？
2. 为什么工具列表属于 Agent Definition 的一部分？
3. 为什么 Agent 运行时必须绑定一个明确版本？
4. 为什么不能让客户端直接传入任意 `dispatch_key`？

---

## 六、阶段三：Tool Calling 与能力目录

### 6.1 为什么 Tool 是平台核心

模型本身不能安全地完成真实业务副作用。它只能提出调用意图，平台负责决定是否允许调用、调用什么以及如何记录结果。

```text
模型提出：我要调用工具 X
  -> 平台读取服务端目录
  -> 校验工具是否存在、启用、可用
  -> 校验主体权限
  -> 校验输入 Schema
  -> 执行固定分发
  -> 脱敏并返回结果
```

### 6.2 概念清单

- `[ ]` Tool Name、Description、Input Schema、Output Schema。
- `[ ]` Tool Registry 与 Tool Discovery。
- `[ ]` 内置工具、HTTP 工具、MCP 工具、知识库工具的区别。
- `[ ]` Tool Calling 的模型侧协议。
- `[ ]` 服务端重新读取工具目录的原因。
- `[ ]` 工具权限与用户权限的关系。
- `[ ]` 工具确认策略：总是确认、条件确认、不需要确认。
- `[ ]` 工具超时、重试和取消。
- `[ ]` 工具幂等和外部副作用。
- `[ ]` 工具输入校验和输出校验。
- `[ ]` 工具错误边界和错误码。
- `[ ]` 工具凭据不能进入 Prompt、日志或公开事件。
- `[ ]` Tool 与 Capability 的统一建模。

### 6.3 当前项目对应的位置

- `app/platform/interaction/domain/capability.py`
- `app/platform/interaction/ports/capability_catalog.py`
- `app/platform/interaction/application/catalog.py`
- `app/platform/interaction/application/agent_call_policy.py`
- `app/platform/interaction/application/agent_dispatch.py`
- `app/interfaces/agent/function_calling_adapter.py`
- `app/interfaces/mcp/` 或相关 MCP 适配目录
- `app/infrastructure/persistence/repositories/platform_capability_repository.py`

当前能力目录已经表达：

- 能力代码。
- 能力类型。
- 输入和输出契约。
- 必填字段。
- 确认策略。
- 权限。
- 超时。
- 错误边界。
- 固定分发键。

### 6.4 从固定注册到平台注册

当前更接近：

```text
代码 / 数据库登记能力
  -> Composition 绑定固定分发器
  -> Runtime 调用能力
```

平台目标是：

```text
平台管理员或系统安装内置工具
  -> 用户从目录选择工具
  -> Agent Definition 保存工具绑定
  -> 发布时再次校验工具版本和权限
  -> Runtime 按服务端绑定执行
```

### 6.5 练习

- `[ ]` 为一个“查询知识库”工具写 Input Schema 和 Output Schema。
- `[ ]` 为一个“生成文件”工具定义成功、失败、超时三类结果。
- `[ ]` 画出模型提出工具调用后，服务端执行前的安全检查链路。
- `[ ]` 说明为什么工具名称、分发键和 Python 函数名不能直接等同。
- `[ ]` 设计一个需要用户确认的“发送邮件”工具。
- `[ ]` 设计一个可重试但必须幂等的“创建报告”工具。

### 6.6 阶段验收

能够回答：

1. 为什么模型的工具调用意图不能直接作为执行授权？
2. 为什么工具需要 Input Schema 和 Output Schema？
3. 为什么同一个工具需要区分权限、确认和幂等？
4. 为什么用户自定义 HTTP 工具不能直接允许任意 URL 访问？

---

## 七、阶段四：Knowledge、RAG 与 Agent

### 7.1 学习目标

理解知识库不是 Agent 的记忆，也不是模型训练。知识库是 Agent 可受控调用的一类外部知识能力。

### 7.2 概念清单

- `[ ]` 文档解析、清洗、结构提取和分块。
- `[ ]` Embedding 和向量检索。
- `[ ]` 关键词检索、向量检索和混合检索。
- `[ ]` 召回、融合、rerank 和证据过滤。
- `[ ]` 文档、版本、章节、chunk、引用之间的关系。
- `[ ]` 知识库发布版本和运行时可见版本。
- `[ ]` 证据不足时为什么不能强行生成结论。
- `[ ]` Agent 如何调用知识库工具。
- `[ ]` 知识库权限如何传递到 Agent。
- `[ ]` 检索结果如何成为下游 Agent 的输入。
- `[ ]` 读取知识库结果时如何保留来源和引用。

### 7.3 当前项目对应的位置

- `app/platform/ingestion/`
- `app/platform/knowledge/`
- `app/business/online/application/rag_facade.py`
- `openspec/specs/` 下 Knowledge、Retrieval 和引用相关规格
- `docs/RAG学习笔记.md`

### 7.4 Agent 使用知识库的两种模式

#### 模式 A：Agent 自主调用检索工具

```text
用户问题
  -> Agent 判断需要资料
  -> 调用 Knowledge Search Tool
  -> 阅读召回证据
  -> 生成回答
```

优点是灵活，缺点是过程更难预测，需要限制调用次数和证据范围。

#### 模式 B：Workflow 先检索，再交给 Agent

```text
用户问题
  -> Knowledge Retrieval Node
  -> Answer Agent
```

优点是输入输出明确，容易审计和复现，更适合 V1 的固定 Workflow。

### 7.5 练习

- `[ ]` 解释“知识库”和“Conversation Memory”的区别。
- `[ ]` 设计一个带引用的知识问答 Agent 输出 Schema。
- `[ ]` 画出检索证据从 Knowledge 到 Agent 再到最终回答的流转。
- `[ ]` 设计证据不足、知识库无权限和知识库版本不存在三种错误。
- `[ ]` 说明为什么下游 Agent 不应只接收一段没有来源的字符串。

### 7.6 阶段验收

能够回答：

1. RAG 解决的是 Agent 的什么问题？
2. 为什么 RAG 不能保证模型一定说真话？
3. 为什么引用和证据需要进入输出契约？
4. 什么时候应该把检索做成 Workflow 节点，而不是让 Agent 自主检索？

---

## 八、阶段五：LangChain 与 LangGraph

### 8.1 先理解职责边界

```text
平台负责：
  Agent Definition、Workflow Definition、权限、版本、持久化、审计、租户隔离

LangChain / LangGraph 负责：
  Prompt 组装、模型调用、工具绑定、消息处理、节点执行、状态图运行能力
```

框架是执行基础，不应该替代平台的产品和领域模型。

### 8.2 LangChain 学习清单

- `[ ]` `ChatModel` 和消息对象。
- `[ ]` Prompt Template。
- `[ ]` Runnable 和链式组合。
- `[ ]` Structured Output。
- `[ ]` Tool 定义与 Tool Binding。
- `[ ]` Tool Calling 消息往返。
- `[ ]` Callback、Streaming 和运行事件。
- `[ ]` LangChain 的错误处理边界。
- `[ ]` LangChain 的状态是否持久化，以及由谁持久化。
- `[ ]` LangChain 对 Provider 的适配方式。
- `[ ]` LangChain 对上下文长度和 Token 成本的影响。

### 8.3 LangGraph 学习清单

- `[ ]` State：图中共享的结构化状态。
- `[ ]` Node：对状态执行一次变换的函数或 Runnable。
- `[ ]` Edge：节点之间的连接。
- `[ ]` Conditional Edge：根据状态决定下一个节点。
- `[ ]` START 和 END。
- `[ ]` Checkpoint：保存图运行状态。
- `[ ]` Interrupt：暂停等待外部输入。
- `[ ]` Resume：从中断位置继续。
- `[ ]` Retry：节点失败后的重新执行。
- `[ ]` Human-in-the-loop。
- `[ ]` 循环和终止条件。
- `[ ]` 并行分支和结果合并。
- `[ ]` LangGraph 状态与平台 Workflow Run 的映射。

### 8.4 需要重点辨析

```text
LangGraph State
  是一次图执行中的运行时状态

Platform Workflow Definition
  是用户配置并发布的流程定义

Platform Workflow Run
  是某个用户、某个版本、某次输入产生的运行事实
```

三者不能混为一个对象。

### 8.5 练习

- `[ ]` 用最小示例写出一个“分析 -> 审核 -> 输出”的 LangGraph。
- `[ ]` 为每个节点定义输入、输出和失败结果。
- `[ ]` 画出 LangGraph State 与平台 Node Run 的对应关系。
- `[ ]` 说明平台为什么不能只保存 LangGraph 的最终结果。
- `[ ]` 说明框架的 Checkpoint 与平台的持久化事件各自解决什么问题。

### 8.6 阶段验收

能够回答：

1. LangChain 和 LangGraph 分别适合解决什么问题？
2. 为什么“使用 LangGraph”不等于“已经有了低代码 Workflow 平台”？
3. 平台如何避免被某个具体框架的类型和状态模型锁死？
4. 为什么 Workflow Definition 和 Workflow Run 必须分开保存？

---

## 九、阶段六：Workflow 基础

### 9.1 Workflow 的定义

Workflow 是一份描述执行结构的定义，至少包含：

```text
Workflow Definition
  = Nodes
  + Edges
  + Node Input Contracts
  + Node Output Contracts
  + Data Mapping
  + Conditions
  + Retry / Timeout Policy
  + Version
```

### 9.2 概念清单

- `[ ]` Node、Edge、DAG。
- `[ ]` Workflow Definition 与 Workflow Run。
- `[ ]` Workflow Version 与运行时版本绑定。
- `[ ]` 节点输入和输出契约。
- `[ ]` 节点之间的数据映射。
- `[ ]` 前置依赖和可执行节点。
- `[ ]` 环检测和不可达节点。
- `[ ]` 串行执行。
- `[ ]` 并行执行。
- `[ ]` 条件分支。
- `[ ]` 汇合和结果聚合。
- `[ ]` 节点失败、跳过、重试和取消。
- `[ ]` Workflow 级失败和节点级失败。
- `[ ]` 中间结果和最终结果。
- `[ ]` Workflow 运行事件和节点事件。
- `[ ]` 幂等键、输入指纹和重放。

### 9.3 当前代码对应的位置

- `app/platform/workflow/domain/models.py`
- `app/platform/workflow/application/service.py`
- `app/platform/workflow/application/registry.py`
- `app/platform/workflow/ports/executor.py`
- `app/platform/workflow/ports/repository.py`
- `app/infrastructure/persistence/models/workflow.py`
- `app/infrastructure/persistence/repositories/workflow_repository.py`
- `app/composition/workflow.py`
- `openspec/specs/workflow-run-and-node-contracts/spec.md`

### 9.4 当前模型应如何理解

当前 Workflow Node 主要是：

```text
node_id
node_type = capability
capability_code
input_fields
output_fields
max_attempts
```

它已经能表达：

- 一个节点绑定一个平台能力。
- 节点有输入输出字段。
- 边可以传递指定输出字段。
- Workflow 必须是无环结构。
- 节点可以失败、重试、取消和跳过。

它还没有完全表达：

- 用户可配置的 Agent Definition 引用。
- Tool、Knowledge、条件和转换节点的专用类型。
- 节点参数配置和表达式。
- 用户可见的草稿和发布流程。
- 多 Agent 专用协作策略。
- 动态 Workflow 创建和编辑 API。

### 9.5 Workflow 与 Task 的边界

```text
Task：一项可持久化、可重试、可取消的工作

Workflow：多个步骤和依赖的组织方式

Workflow Run：一次 Workflow 执行
Node Run：Workflow 中一个节点的一次执行
```

不要把所有内部函数都拆成 Task。适合成为独立节点的步骤通常具备至少一个特点：

- 需要独立重试。
- 需要独立结果。
- 需要人工等待或审批。
- 需要独立权限。
- 需要跨服务或跨 Worker 执行。
- 需要在流程图中展示。

### 9.6 练习：设计一个四节点 Workflow

使用 Tender 作为例子，但只关心平台结构：

```text
输入文件
  -> 需求分析 Agent
  -> 格式提取 Agent
  -> 边界校验 Agent
  -> 骨架生成 Agent
```

为每个节点写出：

- 节点 ID。
- 节点类型。
- 输入字段。
- 输出字段。
- 依赖的上游节点。
- 失败策略。
- 是否允许重试。
- 是否需要保存中间结果。

### 9.7 阶段验收

能够回答：

1. 为什么 Workflow 必须版本化？
2. 为什么节点之间应传递结构化字段，而不是默认共享全部上下文？
3. 为什么 DAG 校验必须在运行前完成？
4. Workflow 失败和某个节点失败有什么区别？
5. Workflow Run 为什么必须绑定创建时的 Definition Version？

---

## 十、阶段七：多 Agent 协作

这是本项目低代码平台目标中的核心学习部分，不能被 Workflow 概念覆盖掉。

### 10.1 多 Agent 协作到底是什么

多 Agent 协作不是“同时调用几个模型”这么简单，而是多个具有明确职责的 Agent 之间发生了：

- 任务分工。
- 输入输出传递。
- 状态或上下文共享。
- 依赖和顺序控制。
- 结果合并。
- 失败处理。
- 权限和预算控制。

### 10.2 多 Agent 与 Workflow 的关系

```text
Workflow 是协作结构。
Agent 是协作参与者。
Runtime 是协作执行者。
```

常见组合：

```text
Workflow A：只有工具节点
Workflow B：一个 Agent + 多个工具
Workflow C：多个 Agent 串行
Workflow D：多个 Agent 并行后汇总
Workflow E：Supervisor 动态选择 Agent
```

因此：

- Workflow 可以不包含多个 Agent。
- 多 Agent 协作通常需要某种流程结构。
- V1 最好把多 Agent 协作先建模为 Workflow 中的多个 Agent 节点。

### 10.3 协作模式一：Pipeline

```text
Agent A -> Agent B -> Agent C
```

适合：职责清楚、顺序稳定、每一步输出是下一步输入的场景。

学习重点：

- `[ ]` 节点输入输出契约。
- `[ ]` 上游输出如何映射为下游输入。
- `[ ]` 上游失败时下游是否跳过。
- `[ ]` 每个节点是否可以独立重试。
- `[ ]` 下游 Agent 是否需要重新读取原始输入。

Tender 示例：

```text
需求分析 Agent
  -> 格式提取 Agent
  -> 边界校验 Agent
  -> 骨架生成 Agent
```

### 10.4 协作模式二：Parallel / Fan-out

```text
              +-> Agent A -+
输入 -> 分发 -+-> Agent B -+-> 汇总 Agent
              +-> Agent C -+
```

适合：多个 Agent 可以独立处理同一输入或不同输入片段的场景。

学习重点：

- `[ ]` 并行节点是否共享输入快照。
- `[ ]` 一个分支失败是否阻断全部流程。
- `[ ]` 汇总 Agent 接收什么结构。
- `[ ]` 并发度如何限制。
- `[ ]` 多个分支如何计算成本和超时。
- `[ ]` 汇总是否需要标注每个分支的来源。

### 10.5 协作模式三：Fan-in / Aggregation

```text
Agent A 输出 a
Agent B 输出 b
Agent C 输出 c
       |
       v
汇总 Agent 输入 {a, b, c}
```

学习重点：

- `[ ]` 汇总输入 Schema。
- `[ ]` 结果顺序是否稳定。
- `[ ]` 部分结果缺失如何表示。
- `[ ]` 汇总 Agent 是否必须知道来源。
- `[ ]` 汇总结果如何去重和冲突处理。

### 10.6 协作模式四：Supervisor

```text
用户请求
   |
   v
Supervisor Agent
   +--> Research Agent
   +--> Writer Agent
   +--> Reviewer Agent
```

Supervisor 负责根据任务动态选择其他 Agent。它更灵活，但也带来更多不确定性：

- `[ ]` Supervisor 如何发现可用 Agent。
- `[ ]` Supervisor 能调用哪些 Agent。
- `[ ]` 如何限制循环和最大步骤数。
- `[ ]` 如何防止 Agent 之间无限互相调用。
- `[ ]` 如何记录动态选择过程。
- `[ ]` 如何复现一次动态决策。
- `[ ]` 如何估算最坏成本。
- `[ ]` 如何让用户理解当前流程走向。

V1 可以学习，但不建议一开始把它作为唯一协作方式。

### 10.7 协作模式五：Handoff

```text
接待 Agent
  -> 判断应该交给哪类专家
  -> 将必要上下文移交给专家 Agent
```

学习重点：

- `[ ]` 移交的是完整上下文还是摘要。
- `[ ]` 移交后原 Agent 是否继续负责。
- `[ ]` Handoff 是否记录目标 Agent 和原因。
- `[ ]` 目标 Agent 是否有权限接收原上下文。
- `[ ]` 如何防止敏感信息越权传播。

### 10.8 协作模式六：Review / Debate

```text
生成 Agent
   |
   v
审核 Agent
   +--> 通过 -> 输出
   +--> 不通过 -> 返工或重试
```

学习重点：

- `[ ]` 审核标准是否结构化。
- `[ ]` 审核结果是否区分错误类型。
- `[ ]` 返工次数如何限制。
- `[ ]` 生成结果和审核结果如何共同保存。
- `[ ]` 多个审核意见冲突时由谁汇总。

### 10.9 V1 推荐顺序

```text
第一优先：Pipeline
第二优先：Parallel + Fan-in
第三优先：Review Loop，限制最大轮次
后续版本：Supervisor
后续版本：自由 Handoff、Debate、Agent Swarm
```

### 10.10 Agent 间传递什么

优先采用显式结构化输入：

```json
{
  "source_document": "attachment-ref-001",
  "requirements": [
    {
      "id": "req-001",
      "text": "...",
      "source": "evidence-ref-001"
    }
  ],
  "previous_result": {
    "status": "completed",
    "output_reference": "artifact-ref-001"
  }
}
```

不要默认这样做：

```text
把所有历史消息、所有 Prompt、所有内部错误和所有工具响应拼成一段长文本，交给下一个 Agent 自己猜。
```

需要掌握的区别：

- `[ ]` 显式字段传递：可校验、可追踪、可复现。
- `[ ]` 共享状态：方便协作，但容易发生隐式依赖和并发冲突。
- `[ ]` 摘要传递：节省 Token，但可能丢失细节。
- `[ ]` 引用传递：适合大文件和中间产物，不把内容复制到每个节点。

### 10.11 多 Agent 的失败语义

为每个节点判断：

- `[ ]` 输入非法：直接失败，通常不重试。
- `[ ]` 权限不足：直接失败，不应重试。
- `[ ]` Provider 瞬时超时：可以按策略重试。
- `[ ]` 工具结果为空：可能需要降级或人工确认。
- `[ ]` 证据不足：返回受控的资料不足，而不是编造。
- `[ ]` 审核不通过：进入有限次数返工。
- `[ ]` 一个并行分支失败：继续汇总、部分成功还是整体失败。
- `[ ]` Supervisor 无法决定下一步：暂停、转人工还是失败。

### 10.12 练习：设计一个多 Agent 流程

设计如下流程，并写出每个节点的输入输出：

```text
用户问题
  -> 需求分析 Agent
  -> 知识检索 Agent
  -> 三个专家 Agent 并行分析
  -> 汇总 Agent
  -> 审核 Agent
  -> 最终回答 Agent
```

必须回答：

1. 哪些节点可以并行？
2. 每个 Agent 的职责边界是什么？
3. 专家 Agent 的结果如何汇总？
4. 某一个专家 Agent 失败怎么办？
5. 审核不通过后是否返工？最多几次？
6. 哪些中间结果需要持久化？
7. 哪些内容只能通过引用传递？
8. 用户在运行过程中能看到什么？

### 10.13 阶段验收

能够回答：

1. Pipeline 和 Supervisor 的主要差异是什么？
2. 为什么多 Agent 不是简单地把多个 LLM 请求并发发出去？
3. 为什么 Agent 之间最好使用显式输入输出？
4. 为什么多 Agent 越自由，越需要运行上限、权限和审计？
5. 如何判断一个场景应该使用单 Agent、Workflow 还是多 Agent？

---

## 十一、阶段八：Agent Definition、Version 和生命周期

### 11.1 为什么必须建模 Definition

如果 Agent 只存在于 Python 类和 Composition 注册表中，平台就只能由开发者修改。低代码平台需要把 Agent 的配置变成可持久化、可验证、可发布的业务对象。

### 11.2 Agent 生命周期

```text
创建草稿
  -> 编辑配置
  -> 校验
  -> 测试运行
  -> 发布 v1
  -> 使用 v1 运行
  -> 编辑生成草稿 v2
  -> 发布 v2
  -> 旧运行仍绑定 v1
```

### 11.3 学习清单

- `[ ]` Agent 身份与版本的区别。
- `[ ]` 草稿是否允许被运行。
- `[ ]` 发布版本是否不可变。
- `[ ]` 版本是否需要保存完整配置快照。
- `[ ]` Agent 下线后历史运行是否仍可查询。
- `[ ]` Workflow 引用 Agent 时引用 Agent ID 还是版本 ID。
- `[ ]` Agent 版本升级是否自动影响已有 Workflow。
- `[ ]` 发布前如何校验工具仍然存在。
- `[ ]` 发布前如何校验知识库权限和版本。
- `[ ]` 发布前如何校验输入输出 Schema。
- `[ ]` 如何回滚到旧版本。
- `[ ]` 如何处理被删除工具、模型和知识库。

### 11.4 推荐的数据关系

```text
Agent
  1 -> N AgentVersion

AgentVersion
  N -> N ToolBinding
  N -> N KnowledgeBinding
  1 -> 1 ModelConfigSnapshot

Workflow
  1 -> N WorkflowVersion

WorkflowVersion
  N -> N AgentVersion / CapabilityVersion
```

运行记录必须保存最终解析出的版本引用，而不是只保存一个会变化的 Agent ID。

### 11.5 练习

- `[ ]` 设计 Agent 和 AgentVersion 的字段表。
- `[ ]` 设计一次发布校验清单。
- `[ ]` 解释为什么修改草稿不能影响正在运行的任务。
- `[ ]` 设计 Agent 被下线后的历史运行行为。
- `[ ]` 设计一个 Agent 回滚场景。

### 11.6 阶段验收

能够回答：

1. 为什么运行记录必须绑定 Agent Version？
2. 为什么发布版本最好不可变？
3. 为什么 Workflow 发布时要解析并冻结 Agent 版本引用？
4. 用户删除 Agent 后，历史 Workflow Run 应该怎么办？

---

## 十二、阶段九：Workflow Definition、校验与发布

### 12.1 Workflow 编辑的完整闭环

```text
新建 Workflow 草稿
  -> 添加节点
  -> 配置节点
  -> 配置输入输出映射
  -> 连接节点
  -> 静态校验
  -> 测试运行
  -> 发布版本
  -> 允许用户运行
```

### 12.2 Workflow 节点类型学习清单

- `[ ]` Agent Node：调用一个 Agent Version。
- `[ ]` Tool Node：调用一个受控工具。
- `[ ]` Knowledge Node：执行检索或知识问答。
- `[ ]` Condition Node：根据结构化状态判断分支。
- `[ ]` Parallel Node：创建多个分支。
- `[ ]` Join Node：等待并合并分支。
- `[ ]` Transform Node：做确定性字段转换。
- `[ ]` Human Review Node：等待用户或人工审核。
- `[ ]` Output Node：规范化最终输出。

V1 不一定要全部实现，但要能说明每种节点的输入、输出、失败和权限边界。

### 12.3 发布前校验

- `[ ]` 节点 ID 唯一。
- `[ ]` 节点类型有效。
- `[ ]` Agent 或 Tool 引用存在。
- `[ ]` 引用的版本处于可用状态。
- `[ ]` 用户拥有使用权限。
- `[ ]` 必填输入字段已被提供。
- `[ ]` 上游输出字段存在。
- `[ ]` 下游输入字段类型兼容。
- `[ ]` 没有环。
- `[ ]` 没有不可达节点。
- `[ ]` 至少存在一个入口和一个出口。
- `[ ]` 条件分支覆盖规则明确。
- `[ ]` 并行分支有汇合或明确允许独立结束。
- `[ ]` 每个节点有超时和重试策略上限。
- `[ ]` 敏感字段不会进入公开事件和日志。
- `[ ]` Workflow 输入输出 Schema 完整。

### 12.4 数据映射学习清单

理解以下三种映射：

```text
1. 上游节点输出 -> 下游节点输入
2. Workflow 输入 -> 第一个节点输入
3. 最后节点输出 -> Workflow 最终输出
```

需要继续学习：

- `[ ]` 字段映射。
- `[ ]` 默认值。
- `[ ]` 可选字段。
- `[ ]` 数组和对象映射。
- `[ ]` 引用映射。
- `[ ]` 模板表达式。
- `[ ]` 映射失败。
- `[ ]` 映射中的敏感字段。
- `[ ]` 用户可见字段与内部字段。

### 12.5 阶段验收

能够画出一个 Workflow 编辑器的状态：

```text
草稿 -> 校验失败
草稿 -> 校验通过 -> 可测试
可测试 -> 发布
发布 -> 可运行
发布 -> 新草稿
```

并说明每个状态允许什么操作、禁止什么操作。

---

## 十三、阶段十：Workflow Runtime 与执行计划

### 13.1 Runtime 的职责

```text
读取已发布 Workflow Version
  -> 创建 Workflow Run
  -> 找到当前可执行节点
  -> 构造节点输入
  -> 调用 Node Executor
  -> 保存节点结果和事件
  -> 解锁后续节点
  -> 处理失败、重试、取消和超时
  -> 结束 Workflow Run
```

### 13.2 Runtime 学习清单

- `[ ]` 如何根据 DAG 找到 ready nodes。
- `[ ]` 如何保证一个 Node Run 不被重复执行。
- `[ ]` 如何持久化每次节点尝试。
- `[ ]` 如何把上游输出转换为下游输入。
- `[ ]` 如何限制并发节点数。
- `[ ]` 如何处理节点超时。
- `[ ]` 如何处理 Workflow 级取消。
- `[ ]` 如何处理节点级取消。
- `[ ]` 如何在重启后恢复运行。
- `[ ]` 如何区分可重试错误和永久错误。
- `[ ]` 如何保存中间结果引用。
- `[ ]` 如何防止旧执行者覆盖新结果。
- `[ ]` 如何保证事件顺序和幂等。
- `[ ]` 如何把运行状态暴露给前端。
- `[ ]` 如何把最终结果回传 Conversation 或 Task。

### 13.3 Workflow 与 Task 的组合方式

需要学习并比较两种模式：

#### 模式 A：Workflow Runtime 内部直接执行节点

```text
Workflow Runtime -> Node Executor -> Agent / Tool
```

适合短步骤和同一运行上下文内的执行。

#### 模式 B：Workflow 节点提交 Task

```text
Workflow Runtime -> Task -> Worker -> Node Executor -> Agent / Tool
```

适合长任务、独立重试、跨进程执行和资源隔离。

必须能说明：哪些节点需要 Task，哪些节点不需要 Task，为什么。

### 13.4 练习

- `[ ]` 手工模拟一个三节点 DAG 的 ready、running、succeeded 状态变化。
- `[ ]` 模拟中间节点失败并重试两次。
- `[ ]` 模拟一个并行分支先后完成后触发 Join。
- `[ ]` 模拟 Worker 重启后 Workflow 如何恢复。
- `[ ]` 设计 Workflow Run 和 Node Run 的事件列表。
- `[ ]` 说明如何避免同一个节点产生两个有效结果。

### 13.5 阶段验收

能够回答：

1. Runtime 和 Workflow Definition 的区别是什么？
2. 为什么 Workflow 不能只依靠前端维护当前节点？
3. 为什么 Node Run 需要独立状态和尝试次数？
4. 一个节点成功后，如何安全地把结果交给下一个节点？
5. Workflow 重启恢复时，如何处理已完成和未完成节点？

---

## 十四、阶段十一：Task、事件、资源和可靠性

### 14.1 学习目标

把当前项目已经存在的 Task Management 能力，理解为 Workflow 和多 Agent 的运行基础，而不是另一个孤立模块。

### 14.2 重点清单

- `[ ]` Task 与 Workflow Run 的区别。
- `[ ]` Attempt 与 Node Attempt 的区别。
- `[ ]` Task Event 与 Workflow Event 的区别。
- `[ ]` lease、续租和过期恢复。
- `[ ]` 幂等键和输入指纹。
- `[ ]` 自动重试和手动重试。
- `[ ]` 协作式取消。
- `[ ]` 过期 Worker 不能覆盖新执行结果。
- `[ ]` 结果资源引用和下载权限。
- `[ ]` owner 隔离。
- `[ ]` 公开投影不能泄露 Prompt、凭据、原始输入和 lease。
- `[ ]` 任务状态与业务结果的区别。

### 14.3 与 Agent 平台的映射

```text
用户运行 Workflow
  -> 创建 Workflow Run
  -> 可能创建一个或多个 Task
  -> Task Worker 执行 Agent 节点
  -> Node Run 保存节点事实
  -> Workflow Run 汇总流程结果
  -> 前端读取运行事件和结果资源
```

### 14.4 练习

- `[ ]` 说明一个 Agent 节点为什么可能需要独立 Task。
- `[ ]` 说明 Task 成功但 Workflow 失败的可能场景。
- `[ ]` 说明 Workflow 取消时如何向下游 Task 传播取消请求。
- `[ ]` 设计用户可见的运行状态和内部事件的差异。

---

## 十五、阶段十二：低代码 Agent Builder

### 15.1 Builder 的用户闭环

```text
创建 Agent
  -> 填写基本信息
  -> 编写 System Prompt
  -> 选择模型
  -> 绑定知识库
  -> 选择工具
  -> 设置输入输出
  -> 在 Playground 测试
  -> 检查调用轨迹
  -> 保存草稿
  -> 发布
```

### 15.2 页面和交互学习清单

- `[ ]` Agent 列表：草稿、已发布、已下线、最近运行。
- `[ ]` Agent 基本信息编辑。
- `[ ]` Prompt 编辑器。
- `[ ]` 模型选择和参数配置。
- `[ ]` 工具选择、搜索和权限提示。
- `[ ]` 知识库选择和版本提示。
- `[ ]` 输入 Schema 编辑。
- `[ ]` 输出 Schema 编辑。
- `[ ]` 运行限制配置。
- `[ ]` Playground 测试。
- `[ ]` 测试时展示工具调用和证据来源。
- `[ ]` 测试结果不自动修改正式版本。
- `[ ]` 发布前校验和错误定位。
- `[ ]` 版本差异和回滚。

### 15.3 Agent Playground 应该展示什么

- `[ ]` 用户输入。
- `[ ]` 使用的 Agent Version。
- `[ ]` 模型调用次数。
- `[ ]` 工具调用名称和安全参数摘要。
- `[ ]` 知识库召回来源和引用。
- `[ ]` 每一步耗时。
- `[ ]` 失败原因和是否可重试。
- `[ ]` 最终结构化输出。
- `[ ]` 不向普通用户暴露系统 Prompt、密钥和内部堆栈。

### 15.4 练习

- `[ ]` 画出 Agent Builder 的页面结构。
- `[ ]` 写出用户创建一个“知识问答 Agent”需要填写的字段。
- `[ ]` 设计 Prompt 校验错误提示。
- `[ ]` 设计工具权限不足时的界面提示。
- `[ ]` 设计“测试草稿”和“运行已发布版本”的差异。

---

## 十六、阶段十三：低代码 Workflow Builder

### 16.1 Builder 的用户闭环

```text
创建 Workflow
  -> 选择输入和输出
  -> 拖入 Agent / Tool / Knowledge 节点
  -> 配置节点
  -> 连接节点
  -> 配置字段映射
  -> 校验 DAG
  -> 测试运行
  -> 查看节点轨迹
  -> 发布
```

### 16.2 编辑器必须学习的概念

- `[ ]` Canvas、Node、Edge、Port。
- `[ ]` 左侧节点面板。
- `[ ]` 节点配置 Inspector。
- `[ ]` 节点输入和输出 Port。
- `[ ]` 字段映射面板。
- `[ ]` 节点校验错误。
- `[ ]` 连线校验错误。
- `[ ]` 自动布局和手动布局。
- `[ ]` 草稿保存。
- `[ ]` Undo、Redo 和未保存提示。
- `[ ]` 测试运行。
- `[ ]` 运行轨迹和节点状态。
- `[ ]` 版本发布。

### 16.3 V1 建议的最小节点集合

```text
输入节点
Agent 节点
Knowledge 检索节点
Tool 节点
条件节点
汇总节点
输出节点
```

不建议一开始加入：

- 任意 Python 代码节点。
- 任意网络访问节点。
- 无上限的循环节点。
- 任意动态执行脚本。
- 不受限制的 Agent-to-Agent 自由调用。

### 16.4 练习

- `[ ]` 设计一个三节点 Workflow 编辑器草图。
- `[ ]` 写出每种节点的最小配置项。
- `[ ]` 设计“端口类型不兼容”的错误提示。
- `[ ]` 设计“节点没有后继、没有入口、存在环”的错误提示。
- `[ ]` 设计运行时从画布节点状态映射到后端 Node Run 状态的方式。

---

## 十七、阶段十四：多 Agent 运行观察和调试

### 17.1 为什么多 Agent 必须可观察

一个最终答案不够说明系统发生了什么。平台用户和开发者需要知道：

```text
Workflow Run
  -> 哪些节点执行了
  -> 每个节点使用哪个 Agent Version
  -> 调用了哪些工具
  -> 检索到了哪些证据
  -> 每一步耗时多少
  -> 哪里失败或重试
  -> 最终结果由哪些中间结果汇总而来
```

### 17.2 运行记录学习清单

- `[ ]` Trace、Span、Run、Event 的区别。
- `[ ]` Workflow Run ID、Node Run ID、Task ID、Conversation ID 的关系。
- `[ ]` Agent 调用链路追踪。
- `[ ]` Tool 调用记录。
- `[ ]` Knowledge 检索记录。
- `[ ]` Token、延迟和成本记录。
- `[ ]` 节点输入输出的脱敏快照。
- `[ ]` 失败错误码和重试原因。
- `[ ]` 用户可见事件和内部调试事件。
- `[ ]` 敏感数据的日志禁止项。
- `[ ]` 运行重放和问题复现。

### 17.3 调试页面至少需要

- `[ ]` Workflow 总状态。
- `[ ]` 当前节点。
- `[ ]` 节点执行顺序。
- `[ ]` 每个节点的状态和耗时。
- `[ ]` 重试次数。
- `[ ]` 安全输入摘要。
- `[ ]` 安全输出摘要。
- `[ ]` 工具和知识调用列表。
- `[ ]` 错误和恢复建议。
- `[ ]` 最终结果资源。

---

## 十八、阶段十五：权限、安全和多租户基础

低代码平台让用户自己配置能力后，安全边界会比固定 Tender Agent 更重要。

### 18.1 权限层次

需要区分：

```text
用户是否能看到 Agent
  -> 用户是否能运行 Agent
  -> Agent 是否能使用工具
  -> Agent 是否能访问知识库
  -> Workflow 是否能引用 Agent
  -> 当前运行是否能读取某个输入和结果
```

### 18.2 学习清单

- `[ ]` 用户、主体、租户、角色、权限的区别。
- `[ ]` Agent 可见权限和运行权限。
- `[ ]` 工具调用权限。
- `[ ]` 知识库访问权限。
- `[ ]` Workflow 编辑权限、发布权限和运行权限。
- `[ ]` Attachment 和 Result Resource owner 隔离。
- `[ ]` Prompt Injection 的基本风险。
- `[ ]` 工具注入和间接 Prompt Injection。
- `[ ]` SSRF、任意 URL 工具和凭据泄露风险。
- `[ ]` 用户输入中的恶意工具调用指令。
- `[ ]` Secret 的存储和运行时注入。
- `[ ]` Prompt、输入、输出、日志脱敏。
- `[ ]` 资源引用不能暴露真实路径。
- `[ ]` Workflow 和 Agent 的发布审批。
- `[ ]` 运行配额、并发限制和成本限制。

### 18.3 练习

- `[ ]` 设计三种角色：普通用户、Agent 创建者、平台管理员。
- `[ ]` 为“发送邮件工具”设计权限和确认策略。
- `[ ]` 设计一个用户无法读取另一个用户 Workflow Run 的测试场景。
- `[ ]` 列出不能写入公开 Event 的十类数据。
- `[ ]` 解释为什么“用户提交的 owner 字段”不能作为真正 owner。

---

## 十九、阶段十六：评测、测试和质量控制

### 19.1 Agent 评测

- `[ ]` 准备固定输入集。
- `[ ]` 定义期望输出结构。
- `[ ]` 定义工具选择是否正确。
- `[ ]` 定义知识引用是否充分。
- `[ ]` 定义拒答和资料不足是否正确。
- `[ ]` 定义成本、延迟和最大调用次数。
- `[ ]` 比较不同 Prompt 和模型版本。
- `[ ]` 记录 baseline。

### 19.2 Workflow 评测

- `[ ]` 正常 Pipeline。
- `[ ]` 并行分支全部成功。
- `[ ]` 并行分支部分失败。
- `[ ]` 条件分支命中不同路径。
- `[ ]` 节点输入映射错误。
- `[ ]` 节点超时。
- `[ ]` 节点重试。
- `[ ]` Workflow 取消。
- `[ ]` Worker 重启恢复。
- `[ ]` 重复提交和幂等。
- `[ ]` 版本冻结和历史运行复现。
- `[ ]` 权限不足。
- `[ ]` 结果资源访问隔离。

### 19.3 多 Agent 评测

- `[ ]` Agent 分工是否符合预期。
- `[ ]` Agent 是否越权调用工具。
- `[ ]` 中间结果是否完整传递。
- `[ ]` 汇总是否遗漏分支结果。
- `[ ]` 审核是否能阻止明显错误。
- `[ ]` 返工是否有最大轮次。
- `[ ]` Supervisor 是否会无限循环。
- `[ ]` 并行执行是否造成不可接受的成本。
- `[ ]` 一个 Agent 失败时整体流程是否有清晰语义。

### 19.4 测试层次

```text
领域测试
  -> Agent / Workflow 定义校验
应用测试
  -> 发布、运行、重试、取消、恢复
协议测试
  -> HTTP / SSE / MCP / Function Calling
集成测试
  -> PostgreSQL、Provider 替身、文件和 Worker
前端测试
  -> Builder、运行状态、错误提示和版本操作
端到端测试
  -> 创建 Agent -> 创建 Workflow -> 发布 -> 运行 -> 读取结果
```

---

## 二十、阶段十七：V1 产品边界

### 20.1 V1 必须掌握并完成的能力

- `[ ]` 用户可以创建 Agent 草稿。
- `[ ]` 用户可以配置 Prompt、模型、工具和知识库。
- `[ ]` Agent 输入输出 Schema 可以保存和校验。
- `[ ]` Agent 可以在 Playground 中测试。
- `[ ]` Agent 可以发布版本。
- `[ ]` 用户可以创建 Workflow 草稿。
- `[ ]` Workflow 至少支持 Agent 节点、Tool 节点、条件和汇总中的核心子集。
- `[ ]` Workflow 可以进行 DAG 和字段映射校验。
- `[ ]` Workflow 可以发布版本。
- `[ ]` Workflow Runtime 可以动态加载已发布版本。
- `[ ]` 至少支持 Pipeline 多 Agent 协作。
- `[ ]` 最好支持有限的 Parallel + Fan-in。
- `[ ]` 节点有独立状态、失败和重试记录。
- `[ ]` Workflow Run 可以查询。
- `[ ]` 节点运行轨迹可以查询。
- `[ ]` Workflow 可以取消或在策略允许时重试。
- `[ ]` 用户只能访问自己有权限的 Agent、Workflow、Run 和结果。
- `[ ]` Tender 可以作为内置 Agent 或模板跑通，证明平台不是只支持空配置。

### 20.2 可以放到 V1.1 或 V2 的能力

- `[ ]` 自由 Supervisor。
- `[ ]` 任意 Agent-to-Agent 动态委派。
- `[ ]` Debate、Swarm 和开放式群聊。
- `[ ]` 任意 Python 代码节点。
- `[ ]` 任意脚本沙箱。
- `[ ]` 复杂循环和递归 Workflow。
- `[ ]` 多租户商业计费和市场分发。
- `[ ]` 完整的 Workflow Marketplace。
- `[ ]` 自动生成整个 Workflow。
- `[ ]` 完全无人工确认的高风险外部副作用。

### 20.3 V1 验收主链路

```text
用户创建 Agent A
  -> 配置知识库和工具
  -> 测试并发布 Agent A v1

用户创建 Agent B
  -> 配置输入输出
  -> 测试并发布 Agent B v1

用户创建 Workflow
  -> Agent A v1
  -> Agent B v1
  -> 配置 A -> B 的字段映射
  -> 发布 Workflow v1

用户运行 Workflow v1
  -> 创建 Workflow Run
  -> A 执行
  -> B 接收 A 的结构化输出并执行
  -> 保存节点事件和结果
  -> 展示最终结果
```

如果这条链路真实跑通，才可以说低代码 Agent 平台 V1 的核心闭环成立。

---

## 二十一、推荐学习顺序总表

| 顺序 | 学习主题 | 重点问题 | 对当前项目的关系 |
| --- | --- | --- | --- |
| 1 | LLM 基础 | 模型负责什么、不负责什么 | 已有 LLM 和 Provider 基础 |
| 2 | Agent 基础 | 一个 Agent 如何工作 | 已有 Agent Runtime 基础 |
| 3 | Tool Calling | 模型如何安全调用能力 | 已有 Capability Catalog 和 Dispatcher |
| 4 | Knowledge / RAG | Agent 如何使用证据 | 已有 Knowledge / RAG |
| 5 | LangChain / LangGraph | 框架如何执行模型和状态图 | 已接入 LangChain，需理解边界 |
| 6 | Workflow 基础 | 节点、边、依赖和版本 | 已有后端 Workflow 契约 |
| 7 | 多 Agent 协作 | Pipeline、Parallel、Supervisor、Handoff | 当前重点学习和后续核心实现 |
| 8 | Agent Definition | 用户如何定义和发布 Agent | 当前主要缺口 |
| 9 | Workflow Definition | 用户如何配置和发布流程 | 当前主要缺口 |
| 10 | Runtime | 如何动态执行用户定义 | 当前只有固定绑定基础 |
| 11 | Task 和可靠性 | 如何异步、重试、取消和恢复 | 当前基础较完整 |
| 12 | Builder | 用户如何在前端配置 | 当前 Workflow 页面还是 mock |
| 13 | 观测和评测 | 如何知道执行是否正确 | 需要随着 Runtime 建设补齐 |
| 14 | 安全和权限 | 用户自定义能力如何受控 | 当前已有安全边界，需要扩展到 Definition |
| 15 | V1 验收 | 哪条链路必须真实跑通 | 用来冻结首版范围 |

---

## 二十二、学习过程中的关键问题清单

每学习完一个阶段，都尝试回答这些问题。不能只回答“概念上是这样”，要结合当前代码和一个实际例子。

### Agent

- `[ ]` Agent 和普通 Chat 的边界是什么？
- `[ ]` Agent 的职责如何避免无限扩大？
- `[ ]` Agent 如何知道自己能调用什么？
- `[ ]` Agent 如何输出下游可使用的数据？
- `[ ]` Agent 为什么需要版本？

### Tool

- `[ ]` Tool 调用谁授权？
- `[ ]` Tool 失败谁负责重试？
- `[ ]` Tool 产生副作用时如何保证幂等？
- `[ ]` Tool 返回什么信息给模型，什么信息只留在内部？

### Workflow

- `[ ]` 哪些步骤应该成为节点？
- `[ ]` 节点之间传递什么？
- `[ ]` Workflow 版本发布后能否被修改？
- `[ ]` 一个节点失败是否需要重跑整个流程？
- `[ ]` 前端和后端谁是真正的运行状态来源？

### 多 Agent

- `[ ]` 为什么这个场景需要多个 Agent，而不是一个 Agent + 多个 Tool？
- `[ ]` Agent 之间是固定顺序还是动态委派？
- `[ ]` 共享上下文是否会导致隐式耦合？
- `[ ]` 一个 Agent 的输出如何被另一个 Agent 验证？
- `[ ]` 多 Agent 的成本和最大调用次数如何控制？

### 低代码平台

- `[ ]` 用户配置的定义如何保存？
- `[ ]` 用户配置的定义如何校验？
- `[ ]` 用户配置的定义如何发布？
- `[ ]` 运行时如何加载用户定义？
- `[ ]` 运行历史如何复现？
- `[ ]` 用户能看到哪些内部过程？
- `[ ]` 哪些能力必须由平台管理员安装，而不能由普通用户自由创建？

---

## 二十三、建议的实际学习项目

不要只做概念笔记。可以按下面的小项目逐步验证理解。

### 小项目一：单 Agent 知识问答

```text
输入问题
  -> 检索知识库
  -> Agent 基于证据回答
  -> 输出答案和引用
```

要验证：Prompt、Tool、RAG、Structured Output、证据不足。

### 小项目二：双 Agent Pipeline

```text
需求分析 Agent
  -> 内容生成 Agent
```

要验证：Agent Definition、输入输出 Schema、字段映射、Workflow Run。

### 小项目三：并行专家分析

```text
输入
  -> 法务 Agent
  -> 技术 Agent
  -> 商务 Agent
  -> 汇总 Agent
```

要验证：并发、Fan-in、部分失败、结果来源和汇总。

### 小项目四：生成与审核

```text
生成 Agent
  -> 审核 Agent
  -> 通过：输出
  -> 不通过：有限次数返工
```

要验证：条件分支、循环上限、审核 Schema、重试和人工介入。

### 小项目五：Tender 平台模板

```text
上传招标文件
  -> 需求分析 Agent
  -> 格式区域 Agent
  -> 边界校验 Agent
  -> 骨架生成 Agent
```

要验证：现有 Tender 能力是否能以平台节点方式被组合，而不是继续写死一条业务调用链。

---

## 二十四、完成度记录区

### 当前阶段

- 当前学习阶段：`阶段一 / 阶段二 / 阶段三 / 阶段四 / 阶段五 / 阶段六 / 阶段七 / 阶段八 / 阶段九 / 阶段十 / 阶段十一 / 阶段十二 / 阶段十三 / 阶段十四 / 阶段十五 / 阶段十六 / 阶段十七`
- 当前最不确定的主题：
- 当前正在阅读的代码：
- 当前待回答的问题：

### 已经能够独立解释

- [ ] 我能区分 LLM、Agent、Tool、Knowledge、Workflow、Task 和 Workflow Run。
- [ ] 我能解释 Workflow 为什么不等于多 Agent。
- [ ] 我能解释 Pipeline、Parallel、Supervisor 和 Handoff 的差别。
- [ ] 我能设计一个 Agent 的输入输出契约。
- [ ] 我能设计两个 Agent 之间的字段映射。
- [ ] 我能画出一次 Workflow Run 的状态变化。
- [ ] 我能解释 Agent Version 和 Workflow Version 为什么必须冻结。
- [ ] 我能说明用户定义的能力为什么不能直接执行任意代码。
- [ ] 我能写出一个低代码 Agent 平台 V1 的最小验收链路。

### 下一次复习记录

```text
复习主题：
仍然不懂的术语：
需要重新阅读的代码：
需要补充的图：
需要完成的练习：
```

---

## 二十五、一句话总纲

```text
先理解 Agent 如何独立完成任务，
再理解 Tool 和 Knowledge 如何扩展 Agent，
再理解 Workflow 如何组织节点，
再理解多个 Agent 如何通过输入输出协作，
最后学习如何把这些定义、版本、权限和运行状态做成用户可操作的平台。
```

当前项目已经把外围底座搭起来了。接下来的学习重点不是继续堆更多业务 Agent，而是把下面这条链路真正理解清楚：

```text
用户定义 Agent
  -> 发布 Agent Version
  -> 用户编排 Workflow
  -> 发布 Workflow Version
  -> Runtime 动态执行
  -> 多 Agent 协作
  -> Task / Event / Artifact 记录
  -> 前端观察、调试和复用
```
