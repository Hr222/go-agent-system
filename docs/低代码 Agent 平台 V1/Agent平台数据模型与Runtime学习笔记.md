# Agent 平台数据模型与 Runtime 学习笔记

> 本文讲低代码平台最容易被忽略、但决定系统能否长期运行的部分：Definition、Version、Run、Node Run、Task、Event、Artifact、发布和动态 Runtime。

---

## 一、为什么要区分“定义”和“运行事实”

低代码平台有两类完全不同的数据：

```text
定义数据
  用户想让系统怎样运行

运行事实
  系统某一次实际上怎样运行了
```

如果混在一起，用户修改配置后，历史运行会被悄悄改变；如果只保存最终结果，系统又无法解释中间发生了什么。

### 1.1 定义数据

包括：

- Agent Definition。
- Agent Version。
- Tool Binding。
- Knowledge Binding。
- Workflow Definition。
- Workflow Version。
- 节点配置。
- 输入输出 Schema。
- 权限和运行策略。

### 1.2 运行事实

包括：

- Agent Run。
- Workflow Run。
- Node Run。
- Task。
- Attempt。
- Event。
- Artifact。
- 错误和重试记录。
- 最终结果资源。

### 1.3 核心原则

```text
定义可以被编辑
发布版本必须冻结
运行必须绑定冻结版本
运行事实不能随草稿变化
```

---

## 二、Agent 的数据模型

### 2.1 Agent 身份

Agent 身份表示一个稳定的用户概念，例如“投标需求分析助手”。它应该有：

- `agent_id`：稳定、不因版本改变。
- `owner_subject` 或租户归属。
- `name`。
- `description`。
- `visibility`。
- 生命周期状态。
- 创建和更新时间。

Agent 身份不应该直接包含本次运行的 Prompt 快照，因为 Prompt 会随版本变化。

### 2.2 Agent Draft

Draft 是用户正在编辑的配置，可能不完整、不能运行或仍然包含错误：

- Prompt 还没写完。
- 工具没有绑定。
- 输出 Schema 不合法。
- 知识库已被删除。
- 节点权限不足。

Draft 可以保存，但不能直接作为正式运行版本，除非产品明确提供“草稿测试”并对测试执行做隔离。

### 2.3 Agent Version

Agent Version 是发布时生成的不可变配置快照，至少要能还原：

- Prompt。
- 模型配置。
- 输入和输出 Schema。
- 工具绑定及其版本或契约。
- 知识库绑定及其可见版本。
- Memory 和 Context 策略。
- 超时、重试、调用次数和成本限制。
- 发布者和发布时间。

运行时不能只保存“Agent ID”，因为 Agent ID 对应的草稿会继续变化。

### 2.4 Agent Run

Agent Run 是一次单 Agent 执行事实，可以独立存在，也可以从属于 Node Run：

```text
Agent Run
  agent_id = knowledge-reviewer
  agent_version = v3
  workflow_run_id = run-001
  node_run_id = node-run-002
  status = succeeded
```

它可以记录：

- 使用的版本。
- 运行主体。
- 输入指纹。
- 结果摘要。
- 调用次数。
- 工具调用数量。
- Token 和耗时摘要。
- 错误代码。

---

## 三、Workflow 的数据模型

### 3.1 Workflow 身份

Workflow 身份表示一个流程概念，例如“招标文件分析流程”。它应该独立于某个版本。

### 3.2 Workflow Draft

Workflow Draft 包含用户当前编辑的图：

- 节点。
- 边。
- 节点配置。
- 字段映射。
- 输入输出 Schema。
- 流程设置。

Draft 允许处于未完成状态，但前端需要明确显示未通过校验的原因。

### 3.3 Workflow Version

发布版本应该是完整、可执行、不可变的快照：

- 所有节点引用都已解析。
- Agent 和 Tool 版本已确定。
- Schema 和字段映射已验证。
- DAG 结构合法。
- 权限和配额已验证。
- 节点策略已冻结。

### 3.4 Workflow Run

Workflow Run 是一次实际运行：

```text
谁运行：owner_subject
运行哪个：workflow_code + workflow_version
输入是什么：安全输入引用或指纹
现在怎样：run_status
跑过什么：events + node_runs
结果在哪：artifact references
```

不能将完整原始输入无条件写入公开运行记录。需要使用受控引用、摘要或输入指纹。

---

## 四、能力目录和用户定义的关系

### 4.1 内置能力

平台可能预先安装：

- Knowledge Search。
- File Read。
- DOCX Render。
- Tender Agent。
- HTTP Request。
- Notification。

内置能力由平台维护分发实现，用户只选择和绑定，不直接修改实现。

### 4.2 用户可配置 Agent

用户可以基于平台能力创建自己的 Agent：

```text
用户 Agent Definition
  -> 绑定内置 Model
  -> 绑定内置 Knowledge
  -> 绑定允许的 Tool
  -> 保存和发布 Agent Version
```

### 4.3 用户自定义 Tool

用户自定义 Tool 比 Agent 更危险，因为它可能连接外部系统。平台需要区分：

- 平台管理员安装的 Tool。
- 租户管理员批准的 Tool。
- 普通用户可使用的 Tool。
- 用户自己的 HTTP / MCP Tool。

用户 Tool 仍然必须经过 URL、凭据、Schema、超时、网络范围、配额和审计限制。

### 4.4 Definition 引用不能只靠字符串

一个节点保存 `capability_code` 只是最小引用。正式平台还需要考虑：

- 引用哪个版本。
- 当前版本是否仍启用。
- 发布时是否冻结。
- 删除后历史运行如何读取。
- 引用方是否有权使用。

可以采用：

```text
capability_id + capability_version
agent_id + agent_version
workflow_id + workflow_version
```

也可以使用不可变发布 ID 作为稳定引用，但必须保证历史对象仍可解析。

---

## 五、发布流程

### 5.1 Agent 发布

```text
Draft
  -> 保存
  -> 静态校验
  -> 权限和引用校验
  -> 创建不可变 Version
  -> Published
```

### 5.2 Workflow 发布

```text
Workflow Draft
  -> 节点和边校验
  -> Schema 和映射校验
  -> Agent / Tool Version 解析
  -> 权限和配额校验
  -> 创建 Workflow Version
  -> Published
```

### 5.3 发布时冻结什么

至少冻结：

- Agent 和 Tool 引用版本。
- Prompt 和模型参数。
- 节点输入输出 Schema。
- 字段映射。
- 超时和重试策略。
- 并发和成本上限。
- 条件分支规则。

### 5.4 发布后修改

发布版本不能原地修改。用户修改时应创建新的 Draft：

```text
Published v1
  -> 编辑
  -> Draft based on v1
  -> 发布 v2
```

这样可以支持版本比较、回滚、历史运行复现和问题排查。

---

## 六、运行时对象和状态机

### 6.1 Workflow Run 状态

可理解为：

```text
queued
  -> running
  -> waiting / accepted
  -> succeeded

running
  -> failed
  -> cancel_requested
  -> cancelled
```

具体状态名称可以不同，但必须定义含义、允许转换和终态。

### 6.2 Node Run 状态

```text
queued
  -> running
  -> accepted
  -> succeeded

running
  -> failed
  -> cancel_requested
  -> cancelled

queued
  -> skipped
```

Node Run 还需要保存：

- 当前尝试次数。
- 最大尝试次数。
- 执行引用。
- 输出摘要或引用。
- 错误代码。
- 更新时间。

### 6.3 accepted 的含义

`accepted` 表示异步执行已经接收：

```text
平台 -> Worker / Task：请处理这个节点
Worker / Task -> 平台：已接收，执行引用为 X
```

此时不能写入成功结果。平台必须等待最终状态或通过恢复机制查询。

### 6.4 终态

终态一旦写入，普通执行流程不应再修改。常见终态：

- `succeeded`。
- `failed`。
- `cancelled`。
- `skipped` 是节点终态，但可能不代表 Workflow 整体结束。

---

## 七、Runtime 的内部模块

### 7.1 Definition Loader

从数据库或定义仓库加载已发布版本。它必须：

- 按稳定 ID 和版本读取。
- 验证版本仍然可用。
- 不读取用户正在编辑的 Draft。
- 处理已下线对象的历史运行读取。

### 7.2 Validator

在运行前检查：

- 版本完整。
- 节点引用有效。
- 输入合法。
- 用户有权限。
- DAG 合法。
- 上游字段可提供下游必填字段。
- 当前配额允许执行。

### 7.3 Planner / Scheduler

Planner 计算下一批 ready nodes；Scheduler 决定何时、在哪里、以什么并发度执行。两者可以是一个模块，也可以分开。

### 7.4 Node Executor

Node Executor 根据节点类型执行：

```text
Agent Node -> Agent Runtime
Tool Node -> Capability Dispatcher
Knowledge Node -> Knowledge Application
Condition Node -> Deterministic Evaluator
Human Node -> Waiting / Approval Service
```

Node Executor 不应该自行改变整个 Workflow 的状态，只返回标准化执行结果，由 Workflow Application 统一推进状态。

### 7.5 State Store

保存：

- Workflow Run。
- Node Run。
- 运行事件。
- 中间输出引用。
- 命令回执。

### 7.6 Recovery Coordinator

处理：

- Worker 崩溃。
- lease 过期。
- accepted 节点长期无结果。
- 重试时间到期。
- 进程重启后未结束的 Run。

### 7.7 Result / Artifact Store

文件、报告、DOCX、图片和大文本不适合全部写在 Run 行里。运行记录应保存不透明资源引用，资源系统负责 owner、绑定关系、下载和生命周期。

---

## 八、执行计划与动态编译

### 8.1 为什么需要执行计划

用户配置的 Workflow 不是直接可运行的 Python 程序。Runtime 需要把它转成执行计划：

```text
Definition
  -> 解析节点和边
  -> 检查依赖
  -> 计算拓扑关系
  -> 解析 Agent / Tool Version
  -> 准备节点执行器
  -> 生成可执行计划
```

执行计划可以是内存对象，但它必须基于已发布版本生成，不能让用户在运行中随意修改。

### 8.2 编译阶段和执行阶段

编译阶段适合做：

- 引用解析。
- Schema 校验。
- 权限检查。
- DAG 检查。
- 节点类型到执行器的映射。

执行阶段适合做：

- 创建 Run。
- 构造输入。
- 调用模型或工具。
- 保存结果和事件。
- 推进状态。

把所有校验都推迟到执行阶段，会导致流程跑到中间才发现配置错误。

---

## 九、事件、审计和可观察性

### 9.1 状态和事件的差异

```text
当前状态：现在是什么情况
事件序列：它是怎么走到这里的
```

例如：

```text
当前 Node Run = failed

事件：
NODE_STARTED attempt=1
NODE_FAILED error=PROVIDER_TIMEOUT
NODE_RETRY_SCHEDULED attempt=1
NODE_STARTED attempt=2
NODE_FAILED error=PROVIDER_TIMEOUT
```

### 9.2 事件设计

事件应该：

- 有序。
- 幂等。
- 带安全元数据。
- 不暴露敏感原文。
- 能解释状态变化。
- 能被前端安全读取。

### 9.3 运行追踪

可以区分：

- Workflow Run：平台流程级。
- Node Run：节点级。
- Agent Run：Agent 调用级。
- Tool Call：工具调用级。
- Model Call：模型调用级。

这些对象可以通过关联 ID 连接，但不需要全部暴露给普通用户。

---

## 十、当前项目的对应关系

当前已有代码可作为概念参照：

| 学习对象 | 当前代码位置 | 当前状态 |
| --- | --- | --- |
| Workflow Definition | `app/platform/workflow/domain/models.py` | 已有固定领域模型 |
| Workflow Run | `app/platform/workflow/domain/models.py` | 已有运行模型 |
| Node Run | `app/platform/workflow/domain/models.py` | 已有节点运行模型 |
| Workflow Event | `app/platform/workflow/domain/models.py` | 已有事件约束 |
| Executor Port | `app/platform/workflow/ports/executor.py` | 已有受控执行契约 |
| Registry | `app/platform/workflow/application/registry.py` | 当前是固定内存注册表 |
| Persistence | `app/infrastructure/persistence/models/workflow.py` | 已有 PostgreSQL 模型 |
| Fixed composition | `app/composition/workflow.py` | 当前只注册固定 Tender 样本 |
| Task Runtime | `app/platform/task/` | 已有生命周期和 Worker 基础 |
| Capability Catalog | `app/platform/interaction/` | 已有能力目录和权限基础 |

关键判断：当前项目已经有“运行事实”的基础，也有固定 Workflow 定义，但“用户定义 -> 保存 Draft -> 校验 -> 发布 Version -> 动态加载”的管理面仍是平台 V1 要补的核心。

---

## 十一、失败一致性问题

### 11.1 执行完成但回写失败

```text
Agent 已经生成文件
  -> Worker 回写 Node Run 失败
  -> 数据库显示节点仍在运行
```

恢复时不能简单再次生成文件，可能造成重复副作用。需要：

- 使用幂等键。
- 保存外部执行引用。
- 查询已有结果。
- 设计结果提交的幂等协议。

### 11.2 状态写成功但事件写失败

状态和事件最好在同一事务中更新，或者有可恢复的事件写入机制，否则用户看到的状态无法由事件解释。

### 11.3 旧 Worker 覆盖新 Worker

lease 过期后可能由新 Worker 接管。旧 Worker 回写时必须校验当前执行引用或 lease，不能只按 Run ID 更新。

### 11.4 重复提交

Workflow Run 创建应支持幂等：

```text
同一主体 + 同一 Workflow Version + 同一 Idempotency Key + 同一输入指纹
  -> 返回同一次运行
```

同一个幂等键但输入不同，应明确报冲突。

---

## 十二、掌握标准

能够独立说明：

1. Definition、Draft、Version、Run 的区别。
2. 为什么 Agent 和 Workflow 发布版本必须不可变。
3. Node Definition 和 Node Run 的区别。
4. Runtime 如何加载定义、规划 ready nodes、调用执行器和推进状态。
5. `accepted` 如何继续推进到最终状态。
6. Task、Event、Artifact 和业务结果的边界。
7. 运行记录为什么需要事件和版本，而不能只保存最终回答。
8. 当前项目已具备不少运行时契约，但还没有完整的动态 Definition 管理面。
