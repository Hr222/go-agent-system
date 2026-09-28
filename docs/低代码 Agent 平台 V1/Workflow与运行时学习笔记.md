# Workflow 与运行时学习笔记

> 本文解释 Workflow 是什么、为什么需要独立建模、如何表达节点依赖、如何执行和恢复，以及它如何承载多 Agent 协作。

---

## 一、Workflow 解决什么问题

一个业务任务经常不是一次函数调用，而是多个有顺序、依赖、分支或等待关系的步骤：

```text
接收文件
  -> 解析文件
  -> 提取信息
  -> 检索知识
  -> 生成结果
  -> 审核结果
  -> 保存产物
```

如果这些步骤只写在一个大函数里，会出现：

- 无法单独查看当前进行到哪一步。
- 某一步失败时只能重跑整个函数。
- 难以并行执行互不依赖的步骤。
- 难以暂停等待人工输入。
- 难以让用户配置和复用流程。
- 难以记录中间结果和审计过程。

Workflow 将这些步骤显式建模为节点和边，使流程可以被检查、保存、执行和观察。

### 1.1 Workflow 与普通业务代码

普通业务代码关注“按程序员写的顺序执行”。Workflow 还要关注：

- 定义是否可被用户编辑。
- 节点是否存在依赖。
- 哪些节点可以并行。
- 哪些节点可以重试。
- 某个节点失败后下游怎么办。
- 运行状态如何保存。
- 进程重启后如何恢复。
- 运行使用哪个版本。

### 1.2 Workflow 不等于多 Agent

Workflow 可以包含：

- 普通工具。
- 文档解析器。
- 知识检索。
- 条件判断。
- 人工审核。
- 一个 Agent。
- 多个 Agent。

只有当多个 Agent 被放在流程中并且发生输入输出、状态或任务分工关系时，才形成多 Agent 协作。

---

## 二、Workflow 的基本对象

### 2.1 Workflow Definition

Workflow Definition 描述流程长什么样，不代表已经执行。它通常包含：

```text
Workflow Definition
  = workflow identity
  + version
  + input schema
  + output schema
  + nodes
  + edges
  + field mappings
  + condition rules
  + retry / timeout policies
```

### 2.2 Workflow Version

发布后的 Version 应该是不可变快照。运行时不能绑定“当前最新配置”，而应该绑定明确版本：

```text
Workflow v1
  使用 Agent A v1

Workflow v2
  使用 Agent A v2
```

如果运行中的 Workflow 读到不断变化的草稿，它可能出现：

- 第一个节点使用旧 Prompt。
- 第二个节点使用新工具集合。
- 运行结果无法复现。
- 失败重试时行为发生改变。

### 2.3 Workflow Run

Workflow Run 是一次真实执行事实，至少应保存：

- Run ID。
- Owner 或主体。
- Workflow Code。
- Workflow Version。
- 输入指纹。
- 当前状态。
- 创建、开始、结束时间。
- 失败信息。
- 最终结果引用。
- 幂等信息。

### 2.4 Node Definition 与 Node Run

Node Definition 是流程中的一个节点配置；Node Run 是该节点在一次 Workflow Run 中的执行事实。

```text
一个 Node Definition
  -> 一次 Workflow Run 中通常有一个 Node Run
  -> 重试时由同一个 Node Run 累加 attempt_count
```

Node Run 需要独立状态，因为用户需要知道到底是哪个节点失败，而不是只看到 Workflow 整体失败。

### 2.5 Edge

Edge 表示节点依赖和数据传递：

```text
source node -> target node
```

边可以附带输出字段：

```text
analysis Agent
  outputs: requirements, evidence
       |
       | requirements, evidence
       v
writer Agent
  inputs: requirements, evidence
```

不建议默认把源节点的所有内部输出都传给目标节点。显式字段映射更容易校验、控制敏感信息和追踪数据来源。

---

## 三、DAG 与节点依赖

### 3.1 为什么通常使用 DAG

DAG 是有向无环图。它允许表达顺序和分支，同时避免无限循环：

```text
A -> B -> C
 \-> D -/
```

Workflow 的 DAG 校验应拒绝：

```text
A -> B -> C -> A
```

有环流程不是绝对不能实现，但必须有明确的循环上限、状态和终止条件。V1 更适合先使用 DAG，审核返工可以用有次数上限的专用循环节点表达。

### 3.2 入度与可执行状态

一个节点什么时候可以执行？通常要满足：

1. 它的所有必需前置节点已经成功。
2. 它需要的输入字段已经可获得。
3. 条件分支允许它执行。
4. 它没有被跳过、取消或已经成功。
5. 当前运行仍处于可继续状态。

```text
ready(node) =
  predecessors_succeeded
  AND inputs_available
  AND condition_matches
  AND node_not_terminal
  AND run_not_cancelled
```

### 3.3 并行节点

如果两个节点只依赖同一个上游结果，且互不依赖，就可以并行：

```text
        -> 技术分析 Agent ->
输入 ->                  -> 汇总 Agent
        -> 商务分析 Agent ->
```

并行不代表无限制地同时执行。平台需要控制：

- 最大并发节点数。
- 单个用户并发数。
- Provider 限流。
- 工具并发安全。
- 汇总等待策略。
- 一个分支失败后的处理方式。

### 3.4 汇合节点

汇合节点需要明确等待条件：

- 所有分支成功后才执行。
- 允许部分成功后执行。
- 任一分支失败立即失败。
- 失败分支以错误对象传入汇总 Agent。

不能只写“等待前面节点完成”，还要定义部分成功和跳过的语义。

---

## 四、节点类型

### 4.1 Agent Node

Agent Node 调用一个已经发布的 Agent Version：

```text
输入字段
  -> 加载 Agent Version
  -> 组装上下文、工具和知识绑定
  -> 执行 Agent
  -> 校验结构化输出
  -> 写入节点结果
```

Agent Node 的失败可能来自模型、工具、权限、输出校验或取消。

### 4.2 Tool Node

Tool Node 直接调用确定性的工具或平台能力。它适合：

- 文档解析。
- 文件转换。
- 知识检索。
- 数据保存。
- 外部 API 调用。

如果一个动作不需要模型判断，做成 Tool Node 通常比让 Agent 自主选择更容易控制。

### 4.3 Knowledge Node

Knowledge Node 执行检索并输出带引用的证据集合。它的优势是流程明确、可审计：

```text
问题 -> 检索 -> 证据集合 -> 下游 Agent
```

### 4.4 Condition Node

Condition Node 应尽量使用确定性规则和结构化字段：

```text
if analysis.status == "multi_volume"
  -> multi-volume branch
else
  -> single-volume branch
```

如果条件完全依赖另一个模型自由判断，应该考虑把判断结果先规范化为结构化字段，再由确定性节点路由。

### 4.5 Human Review Node

人工节点需要持久化等待状态，而不能靠进程阻塞：

```text
节点进入 waiting_review
  -> 创建待审核记录
  -> 用户或审核人提交决定
  -> 校验审核权限
  -> 继续、拒绝或返工
```

### 4.6 Transform Node

Transform Node 做确定性的数据变换，例如字段重命名、数组过滤和格式转换。它能减少“让模型做简单数据搬运”的浪费，也更容易测试。

### 4.7 Join / Aggregate Node

Join Node 等待多个分支，Aggregate Node 负责把多个结构化结果合并为下游输入。两者可以合并成一个实现，但概念上需要区分“等待”和“合并”。

---

## 五、输入输出映射

### 5.1 三种输入来源

节点输入通常来自：

1. Workflow 的初始输入。
2. 上游节点的输出。
3. 系统提供的运行元数据或受控上下文。

```text
Workflow Input
  -> node-a.input

node-a.output.requirements
  -> node-b.input.requirements

system.execution_reference
  -> 仅供内部执行器使用，不暴露给模型
```

### 5.2 显式映射的优势

- 可以在发布前检查字段是否存在。
- 可以限制敏感字段传播。
- 可以知道下游结果来源。
- 可以在前端展示连线含义。
- 可以为中间输出做版本和类型兼容检查。

### 5.3 映射失败

映射失败通常是永久配置错误，不应该无限重试。常见原因：

- 上游未声明字段。
- 下游未声明输入。
- 类型不兼容。
- 必填字段未连接。
- 条件分支导致字段可能不存在。
- 运行时结果结构不符合声明。

---

## 六、Workflow Runtime

### 6.1 Runtime 的主要步骤

```text
1. 读取已发布 Workflow Version
2. 校验主体是否有权运行
3. 创建 Workflow Run
4. 创建或计算节点状态
5. 找到 ready nodes
6. 为节点构造输入快照
7. 调用 Node Executor
8. 处理 completed / accepted / failed
9. 写入 Node Run 和事件
10. 解锁后继节点
11. 判断是否完成、失败、取消或等待
12. 保存 Workflow Run 终态
```

### 6.2 completed、accepted、failed

当前项目的 Workflow Executor 契约已经区分这三类结果：

- `completed`：节点在当前执行中完成，并返回安全摘要和输出引用。
- `accepted`：节点已被异步系统接收，只有不透明执行引用，还没有最终结果。
- `failed`：节点失败，返回受控错误码和是否可重试信息。

这个区别很重要：

```text
accepted != succeeded
```

如果一个 Agent 节点提交了后台 Task，只能说明任务已接收。Workflow 需要等待 Task 完成或通过回调、轮询和事件推进，不能把 accepted 当成最终成功。

### 6.3 节点重试

重试策略至少包含：

- 最大尝试次数。
- 可重试错误集合。
- 退避时间。
- 是否重新构造输入。
- 是否复用上一次中间结果。
- 是否允许从节点起点重跑。
- 重试耗尽后的流程状态。

不能因为模型输出失败就无条件重试。若失败来自权限、输入或固定配置，重试不会改变结果。

### 6.4 取消

Workflow 取消通常是协作式的：

```text
用户请求取消
  -> Workflow Run = cancel_requested
  -> 向运行中的节点发取消请求
  -> 节点在安全点停止
  -> Node Run = cancelled
  -> Workflow Run = cancelled
```

已经完成的节点不能被“取消回滚”。如果节点已经产生外部副作用，需要单独设计补偿操作。

### 6.5 恢复

进程或 Worker 重启后，Runtime 需要根据持久化事实决定：

- 已成功节点保持成功。
- 有效 lease 的节点继续等待或由原 Worker 处理。
- 过期 lease 的节点进入恢复策略。
- `accepted` 节点查询异步执行结果。
- 重试等待时间已到的节点重新进入可执行状态。
- 状态不一致时记录受控错误并阻止盲目重复副作用。

---

## 七、Workflow 与 Task 的关系

### 7.1 Task 不是 Workflow

```text
Task
  管理一项可持久化工作的生命周期

Workflow
  管理多个节点之间的结构和依赖
```

一个 Task 可以是 Workflow 中的一个节点执行载体；一个 Workflow Run 也可以在同一进程中直接执行多个短节点。

### 7.2 什么时候使用 Task

适合独立 Task 的节点：

- 执行时间较长。
- 需要独立 Worker。
- 需要 lease 和恢复。
- 需要单独重试。
- 会产生文件或外部副作用。
- 需要独立进度和结果资源。

不一定需要独立 Task 的步骤：

- 简单字段转换。
- 很短的条件判断。
- 当前 Agent 内部的 Prompt 组装。
- 不产生独立业务事实的轻量校验。

### 7.3 当前项目的基础

当前项目已经有：

- `app/platform/task/` 的状态机、Attempt、Event、Worker 和恢复。
- `app/platform/workflow/` 的 Workflow Run、Node Run、事件和执行器契约。
- `app/infrastructure/persistence/models/workflow.py` 的持久化模型。
- `app/composition/workflow.py` 的固定 Workflow Version 注册。

当前缺的重点不是 Task 生命周期，而是把固定注册的 Workflow 变成用户可定义、可发布和可动态执行的流程。

---

## 八、Workflow 作为多 Agent 协作骨架

### 8.1 Pipeline

```text
Agent A -> Agent B -> Agent C
```

Runtime 每次保存上一个节点的结构化输出，再构造下一个节点的输入。

### 8.2 Parallel + Fan-in

```text
              -> Agent A -+
输入 -> 分发 -+-> Agent B -+-> 汇总 Agent
              -> Agent C -+
```

Runtime 需要决定：

- 分支是否独立提交。
- 是否并行运行。
- 部分失败是否允许汇总。
- 汇总输入如何表示缺失分支。
- 汇总节点何时 ready。

### 8.3 Review Loop

```text
生成 Agent -> 审核 Agent
                 |
          通过 --+-- 不通过 -> 生成 Agent
```

这不是普通 DAG 的无条件环。平台需要记录循环次数并设置上限：

```text
review_attempt < max_review_attempts
```

### 8.4 Supervisor

Supervisor 可以作为一个特殊 Agent Node，根据结构化任务状态决定下一步 Agent。但在平台设计中，必须限制它的可选范围、调用次数、循环次数和权限，否则流程很难复现。

---

## 九、当前代码的学习问题

阅读这些文件：

- `app/platform/workflow/domain/models.py`
- `app/platform/workflow/application/service.py`
- `app/platform/workflow/application/registry.py`
- `app/platform/workflow/ports/executor.py`
- `app/infrastructure/persistence/repositories/workflow_repository.py`
- `app/composition/workflow.py`
- `openspec/specs/workflow-run-and-node-contracts/spec.md`

逐个回答：

1. 当前 Node Type 为什么只有 `capability`？
2. Node 如何引用能力目录？
3. 输入字段和输出字段在哪里校验？
4. 边如何限制只能引用已声明字段？
5. 如何检测环？
6. Node Run 如何记录 attempt_count？
7. `accepted` 和 `completed` 的安全边界是什么？
8. Workflow Version 为什么在 Composition 中固定注册？
9. 当前代码为什么还不是用户可配置 Workflow？
10. 如果添加 Agent Node，应该引用 Agent ID 还是 Agent Version ID？

---

## 十、掌握标准

学习完本文后，应能：

- 画出 Workflow Definition、Workflow Run、Node Definition、Node Run 的关系。
- 解释 DAG、并行、汇合和条件分支。
- 设计节点输入输出映射。
- 说明节点失败和 Workflow 失败的区别。
- 说明 `accepted` 不等于 `succeeded`。
- 说明 Workflow 如何使用 Task、lease、重试和取消。
- 说明为什么用户定义的 Workflow 需要发布版本。
- 说明 Workflow 如何承载 Pipeline、Parallel 和 Review 类型的多 Agent 协作。
- 说明当前项目已有 Workflow 后端契约，但仍缺少动态 Definition、Builder 和多 Agent Runtime 的产品闭环。
