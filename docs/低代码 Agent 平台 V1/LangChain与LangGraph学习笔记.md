# LangChain 与 LangGraph 学习笔记

> 本文用于理解 LangChain、LangGraph 和平台自身 Runtime 的关系。重点不是记 API，而是理解哪些职责应该交给框架，哪些职责必须留在平台。

---

## 一、先建立正确定位

### 1.1 框架不是平台

LangChain 和 LangGraph 可以帮助开发者调用模型、组织消息、绑定工具、定义节点和运行状态图，但它们本身不自动提供完整的低代码平台。

```text
LangChain / LangGraph
  解决：如何执行模型、Prompt、Tool 和图节点

你的平台
  解决：用户如何定义、保存、授权、发布、运行和观察 Agent / Workflow
```

一个框架可以让开发者很快写出一个 Agent，但低代码平台还要回答：

- 谁创建了这个 Agent？
- 这个 Agent 属于谁？
- 当前运行用的是哪个版本？
- 它可以调用哪些工具？
- 工具凭据从哪里来？
- 运行失败后如何重试？
- 用户如何编辑 Workflow？
- 如何查看和审计运行过程？
- 如何保证旧版本运行不受新草稿影响？

这些问题不能简单交给框架默认行为。

### 1.2 当前项目中的实际接入边界

当前项目已经在 LLM Infrastructure 中使用 LangChain 相关适配：

- `langchain_core.messages` 用于消息对象。
- `langchain_openai.ChatOpenAI` 用于 OpenAI-compatible 客户端能力。
- `app/infrastructure/llm/` 中存在 LangChain Chat 和 Structured Output 适配器。
- `app/composition/llm.py` 负责选择和组装具体适配器。

这说明 LangChain 已经作为模型适配和消息调用基础接入，但不能据此判断平台已经具备动态 LangGraph Workflow 或低代码编排器。

---

## 二、LangChain 的核心概念

### 2.1 Message

消息是模型输入的基本单位，常见角色包括：

- System：系统规则和 Agent 职责。
- Human：用户输入。
- AI：模型输出。
- Tool：工具执行结果。

一次工具调用往往是：

```text
HumanMessage
  -> AIMessage(tool_calls=[...])
  -> ToolMessage(result=...)
  -> AIMessage(final answer)
```

重要的是：Tool Message 表示工具执行结果，不代表结果天然可信。平台仍应控制工具返回内容如何进入上下文，是否需要脱敏，是否保留来源。

### 2.2 Prompt Template

Prompt Template 把固定规则和运行时变量组合起来：

```text
固定 System Prompt
  + Agent 配置
  + 当前用户输入
  + Conversation Context
  + Knowledge Evidence
  + Tool Result
```

低代码平台中，Prompt Template 的变量来源必须清楚。不要允许用户在 Prompt 中随意读取任意内部对象。模板变量应来自声明的输入字段、上下文字段或节点输出。

### 2.3 Runnable

Runnable 可以理解为可组合的执行单元。多个 Runnable 可以连接成链：

```text
输入解析 Runnable
  -> Prompt Runnable
  -> Model Runnable
  -> Parser Runnable
```

Runnable 的组合很方便，但平台需要额外保存每一步的定义、版本和事件。只存在内存链中的执行步骤，无法直接支持用户编辑、历史复现和跨进程恢复。

### 2.4 Structured Output

LangChain 可以帮助把模型输出绑定到结构化 Schema 或 Pydantic 模型，但平台仍需负责：

- Schema 的持久化。
- 发布前校验。
- 版本冻结。
- 业务规则校验。
- 错误和重试策略。
- 向下游节点的映射。

框架解析成功只说明“输出形状可解析”，不说明“业务语义正确”。

### 2.5 Tool

框架中的 Tool 通常包含名称、描述、参数 Schema 和执行函数。低代码平台不能直接把用户提交的任意执行函数当成 Tool，而应将 Tool 映射到平台安全目录中的固定能力。

```text
框架 Tool
  -> 负责向模型描述可调用操作

平台 Capability
  -> 负责登记、授权、审计和固定分发
```

两者可以通过适配器连接，但不应混成一层。

---

## 三、LangChain Agent 的执行模型

### 3.1 基本循环

```text
构造 Prompt
  -> 调用 Chat Model
  -> 判断是否有 tool_calls
  -> 没有：解析最终输出
  -> 有：执行工具
  -> 把 ToolMessage 加回消息列表
  -> 再次调用模型
```

### 3.2 为什么平台不能完全依赖框架循环

框架循环解决“怎么继续调用”，平台还要解决：

- 运行上限。
- 取消信号。
- 任务租约。
- 工具权限。
- 用户确认。
- 节点状态。
- 重试和恢复。
- 中间结果资源。
- 版本和审计。

如果执行循环完全由框架内部掌握，平台可能只看到一个黑盒函数：开始时调用，结束时得到结果。这样很难实现用户需要的运行观察和可靠恢复。

### 3.3 推荐的分层方式

```text
Platform Agent Runtime
  -> 读取 Agent Version
  -> 校验主体和绑定
  -> 创建受控 Agent Execution Context
  -> 调用 LangChain Adapter
  -> 接收标准化事件和结果
  -> 保存平台运行事实
```

LangChain Adapter 负责把平台的模型、消息、工具契约转换为框架对象；它不应该直接访问平台 Repository，也不应该自己决定用户权限。

---

## 四、LangGraph 的核心概念

### 4.1 State

State 是一次图运行中节点共享或传递的结构化状态。它可以包含：

- 用户输入。
- 当前任务状态。
- 已完成节点的输出。
- 待处理的工作项。
- 审核结果。
- 路由判断。

State 不是数据库中的永久实体，也不是自动等同于 Conversation Memory。平台应该规定哪些 State 字段需要持久化、哪些只存在于当前执行上下文。

### 4.2 Node

Node 是对 State 执行一次处理的单元，可以是：

- 一个 LLM 调用。
- 一个 Agent。
- 一个 Tool。
- 一个确定性转换函数。
- 一个条件判断。
- 一个人工审核等待点。

在低代码平台中，Node 还需要一个用户可理解的配置引用和输入输出契约。

### 4.3 Edge

Edge 描述节点之间的连接：

- 固定边：A 成功后进入 B。
- 条件边：根据状态进入 B 或 C。
- 并行边：同一输入分发到多个节点。
- 汇合边：等待多个前置节点后继续。

### 4.4 Checkpoint

Checkpoint 保存图运行过程中的状态快照，用于暂停、恢复、调试或回放。它解决的是“框架图运行状态怎么保存”的问题。

平台仍然需要保存自己的 Workflow Run、Node Run 和事件，因为：

- 用户需要看到运行历史。
- 权限系统需要查询资源归属。
- 任务系统需要处理 lease 和 Worker。
- 审计需要知道版本、主体和结果引用。
- 平台不能把所有业务事实藏在框架私有格式中。

### 4.5 Interrupt 和 Resume

中断适用于：

- 等待用户确认。
- 等待人工审核。
- 等待外部系统回调。
- 等待补充附件。

中断必须有明确的状态和恢复入口：

```text
RUNNING
  -> WAITING_INPUT
  -> 收到合法输入
  -> RESUMING
  -> RUNNING
```

不能只依赖进程内协程一直挂起。进程重启、Worker 迁移和用户长时间不操作都要求状态持久化。

---

## 五、LangGraph 与平台 Workflow 的映射

### 5.1 三层对象

```text
平台 Workflow Definition
  用户编辑的流程定义，可版本化、可发布

LangGraph Compiled Graph
  Runtime 根据定义构造出的框架执行对象

平台 Workflow Run
  某主体使用某个发布版本产生的一次运行事实
```

三者的关系是：

```text
Workflow Definition
  -> Validate
  -> Compile / Adapt
  -> LangGraph Graph
  -> Execute
  -> Platform Workflow Run + Node Runs + Events
```

### 5.2 为什么不能直接把 LangGraph 图保存成产品定义

直接保存框架图会有几个问题：

- 框架对象不是稳定的产品数据模型。
- 用户无法安全编辑任意 Python Callable。
- 权限、版本和引用关系不够明确。
- 框架升级可能改变序列化格式。
- 动态用户配置很难映射到任意函数。
- 公开 API 会暴露实现细节。

更稳定的做法是保存平台自己的声明式 Definition，再由 Runtime 将它编译为框架可执行图。

### 5.3 一个概念性映射

```text
平台 Agent Node
  -> 加载 Agent Version
  -> 构造 LangChain Model / Prompt / Tools
  -> 作为 LangGraph Node 执行
  -> 输出结构化字段

平台 Condition Node
  -> 编译为条件 Edge

平台 Parallel / Join
  -> 编译为多分支和汇合结构

平台 Human Review Node
  -> 编译为 Interrupt / Resume 边界
```

### 5.4 映射中的风险

- 平台 Schema 和框架 Schema 不兼容。
- 框架允许的任意 Callable 超出平台安全范围。
- 框架内部重试和平台重试重复，造成多次副作用。
- 框架状态和平台状态不一致。
- 框架执行完成但平台回写失败。
- 平台取消时框架调用仍在运行。

必须明确谁是最终状态来源、谁负责重试、谁负责取消和谁负责持久化。

---

## 六、LangChain / LangGraph 的运行事件

### 6.1 事件层次

```text
Workflow Run
  -> Node Started
  -> Agent Model Call Started
  -> Tool Call Started
  -> Tool Call Completed
  -> Model Call Completed
  -> Node Succeeded
  -> Workflow Succeeded
```

框架事件更细，平台事件更稳定。平台不需要把每一个框架内部回调原样暴露给用户，但应把有产品意义的事实归一化。

### 6.2 建议保留的信息

- Run ID。
- Node Run ID。
- Agent Version。
- Tool Capability Code。
- 事件类型。
- 开始和结束时间。
- 安全的状态和错误码。
- Token 和延迟摘要。
- 结果资源引用。
- 输入输出指纹。

不应公开或长期保存：

- API Key。
- 原始 Authorization Header。
- 数据库连接串。
- 内部文件绝对路径。
- 未脱敏的真实业务附件。
- 不必要的完整 Prompt 和原始 Provider 响应。

---

## 七、如何学习和判断框架 API

阅读一个 LangChain 或 LangGraph API 时，按下面顺序问：

1. 它代表的是定义、运行时对象，还是一次结果？
2. 它是否包含不可序列化的 Python 对象？
3. 它是否隐式执行模型或工具调用？
4. 它的错误如何返回？
5. 它能否被取消？
6. 它的状态在哪里保存？
7. 它是否自动重试？
8. 它是否会把敏感输入写入日志？
9. 它的版本如何绑定？
10. 它如何映射到平台的 Domain、Application 和 Infrastructure 分层？

---

## 八、与当前项目的代码学习方法

### 8.1 先看适配器

重点文件：

- `app/infrastructure/llm/openai_client_factory.py`
- `app/infrastructure/llm/openai_compatible_chat_adapter.py`
- `app/infrastructure/llm/openai_compatible_structured_adapter.py`
- `app/infrastructure/llm/langchain_deepseek_chat_adapter.py`
- `app/infrastructure/llm/langchain_glm_chat_adapter.py`
- `app/infrastructure/llm/langchain_deepseek_adapter.py`
- `app/infrastructure/llm/langchain_glm_adapter.py`

阅读问题：

- LangChain 类型是否泄漏到 Domain？
- Provider 响应如何转换为平台标准结果？
- 流式消息如何转换？
- Structured Output 失败如何映射？
- 历史消息角色如何保持？
- Provider 的重试是否和平台重试分离？

### 8.2 再看架构边界测试

`tests/architecture/test_architecture_boundaries.py` 中对 `langchain` 和 `langgraph` 的限制很重要。它体现了一个原则：

```text
具体框架可以进入适配层，
但不应渗透到 Domain 和不该依赖它的 Application 层。
```

这不是为了拒绝使用框架，而是为了让平台保留替换框架和控制领域模型的能力。

### 8.3 最小实验

先不引入复杂平台代码，分别做四个小实验：

1. 一个普通 Chat Model 调用。
2. 一个 Structured Output 调用。
3. 一个带工具的单 Agent 调用。
4. 一个“分析 -> 审核 -> 输出”的状态图。

每个实验都记录：输入、输出、错误、调用次数、状态、取消方式和持久化位置。

---

## 九、掌握标准

学习完本文后，应能清楚说明：

1. LangChain 是模型、消息、Prompt 和工具执行的适配与组合框架。
2. LangGraph 是状态图、节点、边、中断和恢复的一种执行框架。
3. 平台自己的 Agent / Workflow Definition 不能直接等同于框架对象。
4. 框架事件需要转换为平台稳定的运行事件。
5. 平台必须掌握权限、版本、任务状态、审计和资源访问。
6. 框架的内部重试、平台的节点重试和外部工具重试必须分层设计。
7. 当前项目已接入 LangChain 适配器，但当前 Workflow 仍然是固定后端契约，不是动态 LangGraph Builder。
