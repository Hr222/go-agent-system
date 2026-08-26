## Context

`agent.md` 是 LLM 和人类协作者进入仓库后的第一份协作契约。它当前已经包含读取上下文、测试、安全和提交规则，但仍把阶段目标、旧目录和不完整的 Agent 语义混在其中。`openspec/config.yaml` 作为 OpenSpec 上下文来源，也保留了旧的 `application/modules` 表述，因此单独更新 `agent.md` 会继续产生冲突。

本 Change 只更新协作规则和 OpenSpec 生成上下文，不改变运行时架构。稳定架构以 `ARCHITECTURE.md` 为准，实际进度以系统看板为准，当前交付范围以 OpenSpec Change 为准。

## Goals / Non-Goals

**Goals:**

- 让 LLM 在开始工作前获得一致、简洁、不会快速过期的项目认知。
- 明确平台能力、业务应用、横向技术层以及 Gateway、Agent Management、Ingestion、Knowledge/RAG 的关键边界。
- 规定讨论、评审、诊断和实施请求的不同处理方式。
- 将中文注释要求变成可执行的工程规则，兼顾可读性和克制性。
- 固化测试、敏感数据检查、OpenSpec 和 Git 提交的可验证流程。
- 让 `agent.md` 与 `openspec/config.yaml` 向 LLM 提供相同的目录和术语。

**Non-Goals:**

- 不在 `agent.md` 中复制完整架构图、所有模块说明或系统进度表。
- 不把某个 Phase、业务路线或当前任务优先级写成长期规则。
- 不修改应用代码、接口、数据库、前端、系统看板或 `ARCHITECTURE.md`。
- 不新增 Agent、Workflow、Task Management、认证或上下文运行时能力。

## Decisions

### 1. 建立事实来源优先级

规则按以下顺序解释仓库信息：

```text
用户当前明确指令
  > agent.md 协作与安全规则
  > ARCHITECTURE.md 稳定架构设计
  > 当前 OpenSpec Change 的范围与需求
  > 系统看板的实际进度与优先级
  > README 的运行和使用说明
  > 代码与测试对当前实现的验证证据
```

如果设计、进度和代码出现差异，LLM 必须报告差异，不能静默地把设计当成已实现，也不能因为代码暂时存在就擅自改变架构基线。

备选方案是把当前阶段写死在 `agent.md` 中；该方案会随看板变化而过期，因此不采用。

### 2. 只保留足够的项目心智模型

`agent.md` 只保留 LLM 做判断所需的最小边界，并链接 `ARCHITECTURE.md` 获取完整细节：

```text
平台能力：LLM、Knowledge/RAG、Ingestion、Conversation、Dialogue、Interaction、
          Agent Management、Attachment、Security
业务应用：online、agents/tender
横向技术：interfaces、infrastructure、composition、shared
```

同时固定以下解释：`ingestion` 是通用资料处理 Pipeline；Knowledge/RAG 独立于 LLM 和业务应用；`online` 使用 Knowledge/RAG；Tender 是业务 Agent；Agent Runtime 属于 Agent Management；Gateway 只处理自然语言控制面；直接 HTTP 接口不必经过 Gateway；Composition Root 只负责组装。

### 3. 将协作过程写成判断协议

LLM 先识别请求属于讨论、评审、诊断还是实施，再决定是否修改文件。实施任务必须先读取相关文档和当前 Change，限定范围，采用仓库已有模式，完成验证后再更新任务状态。用户只要求讨论或查看时，不得主动编辑文件。

### 4. 规定中文注释的使用边界

新增或修改代码时，以下内容必须使用简洁、准确的中文注释或中文说明：

- 复杂函数、关键流程和跨模块协调。
- 非直观业务规则、安全边界和兼容逻辑。
- 容易被误改的重要取舍、失败处理和临时限制。

直白的变量赋值、简单分支和可由代码直接表达的逻辑不添加逐行注释。注释说明“做什么”和必要的“为什么”，不翻译代码，不制造重复叙述。

### 5. 将 Git 交付作为显式安全步骤

提交前必须检查工作区、暂存区和差异内容，使用显式路径暂存。提交标题统一采用 `分类（模块）：简洁的中文动作描述`，一次提交只包含一个相互关联的变更。`.tmp`、`.runtime`、`backups`、真实 SQL 备份、OCR 输出、`.env` 和真实业务资料即使位于工作区，也不得进入提交。

实现型 Change 的推荐顺序为：任务完成、测试通过、更新任务、归档 Change、检查暂存区、提交；远程推送仍必须等待用户明确指令。

### 6. 同步 OpenSpec 上下文

`openspec/config.yaml` 只保留稳定的项目事实、当前目录、平台/业务边界和文档职责，不写入具体阶段进度。它与 `agent.md` 使用同一组术语，并明确 OpenSpec 规格只描述当前 Change 的行为范围。

## Risks / Trade-offs

- [规则过长导致 LLM 忽略重点] -> 移除重复架构细节和固定阶段内容，使用短规则与链接。
- [规则与架构再次分叉] -> 只保留最小心智模型，完整模块边界始终引用 `ARCHITECTURE.md`。
- [中文注释过度膨胀] -> 明确“复杂和非直观逻辑必须注释，直白代码不逐行注释”。
- [敏感文件再次被批量暂存] -> 要求显式暂存和提交前检查，列出 `.tmp`、`backups`、真实 SQL 备份和 OCR 输出等具体风险目录。
- [OpenSpec 继续注入旧路径] -> 在同一 Change 中同步更新 `openspec/config.yaml`。

## Migration Plan

1. 重写 `agent.md`，移除固定阶段、旧架构重复内容和不准确的 Agent 表述。
2. 更新 `openspec/config.yaml` 的项目上下文和术语。
3. 使用文档扫描检查旧路径、旧术语、阶段状态和错误的 OpenSpec 名称。
4. 运行 OpenSpec 严格校验、Markdown 检查和 `git diff --check`，再由人工确认规则可执行。

无代码、数据库、接口或部署迁移；回滚只需恢复两份规则文件。

## Open Questions

无。
