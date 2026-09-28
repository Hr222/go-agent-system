# 多 Agent 协作学习笔记

> 本文专门讲多个 Agent 如何分工、传递信息、并行执行、汇总、审核和动态委派。它与 Workflow 学习笔记相关，但不是同一个主题：Workflow 描述执行结构，多 Agent 描述参与协作的智能执行单元。

---

## 一、为什么需要多个 Agent

一个 Agent 当然可以通过更长的 Prompt 和更多工具完成很多任务，但把所有职责都塞进一个 Agent 会产生问题：

- Prompt 变得庞大且互相冲突。
- 工具权限过宽。
- 输出格式不稳定。
- 错误难以定位。
- 不同专业判断互相干扰。
- 很难独立测试某一部分。
- 很难并行处理。
- 一个步骤失败时只能重跑整体。

多 Agent 的价值不是“Agent 数量越多越先进”，而是把不同职责分开，使每个 Agent 更容易理解、限制和验证。

### 1.1 什么时候不需要多 Agent

如果任务只是：

- 一个明确的 Prompt。
- 一次工具调用。
- 一次知识检索后回答。
- 没有独立的专业分工。
- 没有中间结果依赖。

那么一个 Agent 或一个普通链路可能更合适。多 Agent 会增加模型调用、延迟、成本、状态管理和失败路径。

### 1.2 什么时候适合多 Agent

适合拆成多个 Agent 的信号包括：

- 不同步骤需要明显不同的系统指令。
- 不同步骤需要不同工具或知识库。
- 不同步骤有独立的输出 Schema。
- 需要并行邀请多个专家分析。
- 需要一个 Agent 审核另一个 Agent。
- 某个步骤需要独立重试或人工审核。
- 用户希望复用某个专业 Agent。

---

## 二、多 Agent 的四个基本问题

任何协作设计都必须先回答：

### 2.1 谁负责什么

每个 Agent 必须有单一、可描述的职责。不要只写“负责处理任务”，应写成：

```text
输入：已解析的招标需求
职责：识别需求、分类、提取证据
不负责：生成最终投标文字、修改源文件
输出：结构化需求列表和证据引用
```

### 2.2 谁把什么交给谁

协作不是把所有上下文都共享给所有 Agent，而是定义数据流：

```text
需求分析 Agent
  output.requirements
  output.evidence
       |
       +----> 格式提取 Agent.input.requirements
       +----> 生成 Agent.input.requirements
```

### 2.3 谁决定下一步

可能由以下对象决定：

- 固定 Workflow 边。
- 条件节点。
- Supervisor Agent。
- 用户或人工审核人。
- 外部事件。

决定者不同，流程的确定性和可观测性也不同。

### 2.4 失败时谁负责

需要明确：

- 当前 Agent 自己重试。
- Node Runtime 重试。
- Workflow 跳过该节点。
- 返回部分结果。
- 转人工。
- 整个流程失败。

不能把“失败后让模型再试一次”当成完整的失败策略。

---

## 三、协作模式一：Pipeline

### 3.1 结构

```text
Agent A -> Agent B -> Agent C
```

Pipeline 最适合 V1，因为依赖关系固定、输入输出清楚、运行路径容易解释。

### 3.2 例子：Tender 需求处理

```text
文件解析
  -> 需求分析 Agent
  -> 格式区域 Agent
  -> 边界校验 Agent
  -> 骨架生成 Agent
```

每个 Agent 的职责可以是：

| Agent | 输入 | 输出 | 不负责 |
| --- | --- | --- | --- |
| 需求分析 | 文档引用 | 需求列表、证据 | 生成骨架 |
| 格式区域 | 文档引用、需求列表 | 格式区域 | 判断所有业务需求 |
| 边界校验 | 提取结果 | 校验结论、问题 | 直接修改原文 |
| 骨架生成 | 需求、格式、校验结果 | 文档骨架资源 | 任意填充业务内容 |

### 3.3 Pipeline 的优点

- 运行路径稳定。
- 每个 Agent 可单独测试。
- 节点输入输出容易校验。
- 失败位置容易定位。
- 版本和审计容易实现。

### 3.4 Pipeline 的问题

- 前一步设计错误可能污染后续所有步骤。
- 顺序固定，灵活性不高。
- 不适合大量互不依赖的专家分析。
- 如果每个步骤都调用模型，成本可能增加。

### 3.5 设计原则

- 尽量让每个节点输出结构化结果。
- 下游只接收需要的字段。
- 每一步保留来源和版本。
- 失败时记录节点级错误。
- 不要为了“多 Agent”而强行拆分简单步骤。

---

## 四、协作模式二：Parallel / Fan-out

### 4.1 结构

```text
                 -> Agent A -+
输入 -> 分发节点 -+-> Agent B -+-> 汇总 Agent
                 -> Agent C -+
```

多个 Agent 独立分析同一个输入，最后由汇总 Agent 或确定性程序合并结果。

### 4.2 适合场景

- 多个专业领域分别分析。
- 多份独立资料分别处理。
- 多个候选方案分别评估。
- 多种检索策略并行召回。
- 生成多个候选答案后再审核。

### 4.3 并行不是简单开多个线程

平台需要明确：

- 每个分支是否读取相同输入快照。
- 分支是否共享可变状态。
- 分支是否使用不同权限。
- 单个分支失败是否影响其他分支。
- 是否有最大并发数。
- 是否有分支级超时。
- 汇总节点何时可以开始。

### 4.4 部分失败策略

常见策略：

| 策略 | 含义 | 适用场景 |
| --- | --- | --- |
| 全部成功 | 任一分支失败则整体失败 | 任何一个专家都不可缺少 |
| 部分汇总 | 成功分支继续，失败分支带错误信息 | 专家意见可以缺失 |
| 降级 | 失败分支使用默认结果或单一 Agent | 允许质量下降但不希望中断 |
| 转人工 | 失败后等待人工处理 | 结果重要且不能自动猜测 |

### 4.5 Fan-out 的结果结构

建议保留来源：

```json
{
  "branches": [
    {
      "branch_id": "technical",
      "agent_version": "technical-review:v2",
      "status": "succeeded",
      "output": {"risks": []}
    },
    {
      "branch_id": "commercial",
      "agent_version": "commercial-review:v1",
      "status": "failed",
      "error_code": "PROVIDER_TIMEOUT"
    }
  ]
}
```

汇总 Agent 需要知道哪些结果成功、哪些失败，而不是只拿到一段混合文本。

---

## 五、协作模式三：Fan-in 与汇总

### 5.1 汇总的两种方式

#### 确定性汇总

由程序合并字段、去重、排序和聚合数值。

优点：可预测、可测试、成本低。

#### LLM 汇总

把多个结构化结果交给一个汇总 Agent，由模型形成结论。

优点：适合综合分析和自然语言组织；缺点是需要更多验证和成本控制。

### 5.2 汇总 Agent 的输入

汇总 Agent 不应该只收到：

```text
专家 A 说了这些，专家 B 说了那些。
```

更好的输入包括：

- 分支 ID。
- Agent Version。
- 结果状态。
- 输出结构。
- 证据引用。
- 失败信息。
- 冲突标记。

### 5.3 冲突处理

多个 Agent 可能给出不同判断。平台需要提前决定：

- 汇总 Agent 自己判断。
- 规则优先级决定。
- 需要额外审核 Agent。
- 交给人工确认。
- 输出冲突而不强行选择。

没有冲突策略时，汇总 Agent 可能只是把矛盾内容写成一段看似顺畅的答案。

---

## 六、协作模式四：Supervisor

### 6.1 结构

```text
用户输入
  -> Supervisor Agent
      -> Research Agent
      -> Writer Agent
      -> Reviewer Agent
      -> 结束或继续
```

Supervisor 负责动态选择下一个 Agent。这种模式可以处理开放任务，但不确定性明显高于固定 Pipeline。

### 6.2 Supervisor 需要管理的状态

- 当前任务目标。
- 已完成步骤。
- 可用 Agent 列表。
- 每个 Agent 的职责和输入输出。
- 已使用工具和成本。
- 失败次数。
- 最大步骤数。
- 下一步候选及选择原因。

### 6.3 Supervisor 的风险

- 选错 Agent。
- 在两个 Agent 之间来回循环。
- 重复调用同一个 Agent。
- 给 Agent 传递不必要的敏感上下文。
- 选择没有权限的 Agent。
- 运行路径难以复现。
- 成本和耗时不可预测。

### 6.4 受控 Supervisor

不要让 Supervisor 直接选择任意代码，而是：

```text
Supervisor 只能选择服务端目录中的 Agent Version
  -> 平台检查是否允许当前 Workflow 使用
  -> 平台检查输入输出兼容性
  -> 平台记录选择结果
  -> 平台执行
```

V1 可以先把 Supervisor 限制为“有限候选 + 最大步骤数 + 固定输出协议”。

---

## 七、协作模式五：Handoff

### 7.1 Handoff 的含义

Handoff 是一个 Agent 把当前工作交给另一个 Agent，常见于：

- 客服转专家。
- 通用助手转领域助手。
- 需求分类后交给不同执行 Agent。

### 7.2 Handoff 要传递什么

不要默认传递所有会话历史。应该定义移交上下文：

```json
{
  "handoff_reason": "需要投标文件结构分析",
  "task_summary": "...",
  "required_inputs": {
    "attachment_ref": "attachment-ref-001"
  },
  "evidence_refs": ["evidence-ref-001"],
  "constraints": ["只处理格式区域"]
}
```

### 7.3 Handoff 的权限风险

源 Agent 能看到的资料不一定目标 Agent 都能看到。平台必须在移交时重新检查：

- 目标 Agent 是否允许接收该任务。
- 目标主体是否有资源权限。
- 哪些字段需要脱敏。
- 是否需要用户确认。

---

## 八、协作模式六：Review、Debate 和有限返工

### 8.1 生成与审核

```text
生成 Agent
  -> 审核 Agent
      -> passed: 输出
      -> rejected: 返工
```

审核 Agent 应输出结构化结果：

```json
{
  "decision": "rejected",
  "issues": [
    {
      "code": "MISSING_EVIDENCE",
      "message": "第 3 项没有对应证据"
    }
  ],
  "required_changes": ["补充引用"]
}
```

### 8.2 有限返工

返工必须有上限：

```text
review_round = 0
while review_round < max_review_rounds:
  generate
  review
  if passed: finish
  review_round += 1
fail or human review
```

如果没有上限，模型可能在“生成不通过 -> 再生成 -> 仍不通过”的循环中消耗大量资源。

### 8.3 Debate 的适用边界

Debate 可以让多个 Agent 针对同一问题提出观点并互相批评，但它会增加：

- 调用次数。
- 延迟。
- 状态复杂度。
- 结果冲突。
- 评测难度。

它更适合作为后续高级能力，而不是低代码平台第一种协作模式。

---

## 九、Agent 之间如何传递上下文

### 9.1 显式字段传递

```text
Agent A.output.requirements
  -> Agent B.input.requirements
```

这是最适合平台的方式，因为能进行 Schema 校验、权限检查和结果追踪。

### 9.2 共享状态

多个 Agent 读取同一个 Workflow State：

```text
State = {
  input,
  analysis,
  evidence,
  review,
  artifacts
}
```

共享状态方便，但如果任何 Agent 都能任意修改所有字段，会出现隐式耦合和并发冲突。建议规定每个节点负责写哪些字段。

### 9.3 摘要传递

长文档和完整历史不适合每次复制。可以传递摘要，但摘要有信息损失风险，需要保存原始证据引用，以便追溯。

### 9.4 引用传递

大文件、中间产物和知识证据更适合传递不透明引用：

```text
artifact-ref-001
evidence-ref-003
attachment-ref-005
```

下游节点需要通过受控接口读取引用，不能直接读取文件系统路径。

---

## 十、多 Agent 的成本和可靠性

### 10.1 成本组成

一次多 Agent 运行的成本可能包括：

- 每个 Agent 的输入 Token。
- 每个 Agent 的输出 Token。
- 工具和检索调用。
- 并行分支数量。
- 重试次数。
- 审核和返工次数。
- 汇总调用。

必须设置 Workflow 级和 Agent 级预算。

### 10.2 可靠性边界

多 Agent 不会自动提高正确率。错误可能被传递和放大：

```text
分析错误
  -> 生成 Agent 信任错误输入
  -> 审核 Agent 没有发现错误
  -> 最终输出看起来完整但事实错误
```

因此需要：

- 中间结果 Schema。
- 证据引用。
- 审核节点。
- 关键字段确定性校验。
- 失败和不确定状态显式表达。

### 10.3 共享上下文的隐患

共享上下文可能造成：

- Agent 读取不该读取的数据。
- Agent 修改其他 Agent 的结果。
- Prompt 注入影响后续所有 Agent。
- 上下文越来越长，成本失控。
- 运行无法复现。

建议采用“最小必要上下文”：每个 Agent 只收到完成职责需要的字段和引用。

---

## 十一、把 Tender 当作多 Agent 学习案例

Tender 不是平台最终边界，但适合用来理解协作：

```text
文档读取 / 解析
  -> 需求分析 Agent
  -> 格式区域提取 Agent
  -> 分册边界校验 Agent
  -> 骨架生成 Agent
  -> 文档渲染 Tool
```

其中并非每一步都必须是 Agent：

- DOCX 读取可以是确定性 Tool。
- 需求分析适合 Agent。
- 格式区域提取可以是 Agent 或专用解析能力。
- 边界校验可以是规则 + Agent。
- 骨架生成可以是 Agent + 文档渲染 Tool。

这正好说明：多 Agent Workflow 不等于“所有节点都交给模型”。好的平台应该允许 Agent、Tool 和规则节点组合。

---

## 十二、当前项目需要建立的判断

阅读当前代码时，分别判断每个能力属于哪一类：

| 当前能力 | 更接近什么 |
| --- | --- |
| `tender.generate_bid_skeleton` | 业务 Agent 能力 |
| `tender.extract_bid_format_section` | 业务 Agent 或结构化处理能力 |
| `tender.verify_extraction_boundary` | 校验 Agent / 规则能力 |
| Attachment 读取 | Tool / 平台资源能力 |
| Knowledge 检索 | Knowledge Tool / Knowledge Node |
| Task Worker | 执行基础设施 |
| Workflow Node | 编排结构 |
| Capability Catalog | 能力登记和授权基础 |

当前 Workflow 绑定一个 Tender Capability 样本，不代表已经实现多个 Agent 的协作。真正的多 Agent 协作需要至少有两个 Agent 节点、明确的数据映射、运行状态和结果传递。

---

## 十三、掌握标准

能够独立说明：

1. 为什么多 Agent 不等于多次模型调用。
2. 什么时候使用单 Agent，什么时候拆成多个 Agent。
3. Pipeline、Parallel、Fan-in、Supervisor、Handoff、Review 的差异。
4. Agent 之间为什么优先传结构化字段和引用。
5. 部分分支失败时有哪些处理策略。
6. 为什么 Supervisor 需要候选范围、循环上限和审计。
7. 为什么审核返工必须有最大轮次。
8. 为什么多 Agent Workflow 还需要 Tool 和规则节点。
9. 当前项目的 Workflow 具备承载多 Agent 的基础，但当前实际注册样本还不是多 Agent 协作闭环。
