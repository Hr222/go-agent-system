# Agent 协作与工程开发约定

本文档是本仓库的人机协作契约，供 AI coding agent、Codex 与人工协作者统一遵守。它约束 LLM 如何理解项目、实施变更、验证结果和交付 Git；它不替代系统架构、项目进度或 OpenSpec 规格。

## 1. 文档职责与事实来源

不同文档记录不同类型的事实，不能互相替代：

| 来源 | 负责内容 |
|---|---|
| 用户当前明确指令 | 本次工作目标、授权范围和优先级。 |
| `agent.md` | 协作方式、工程守则、安全约束、验证和 Git 交付规则。 |
| `ARCHITECTURE.md` | 稳定的系统架构、模块边界、依赖方向和关键运行时链路。 |
| 当前 OpenSpec Change | 本次变更的需求、设计、任务和验收条件。 |
| `docs/go agent system - 系统看板.md` | 实际进度、当前优先级和阶段计划。 |
| `README.md` | 项目用途、环境、运行方式和接口入口。 |
| 代码与测试 | 当前实现行为和验证证据。 |

用户指令优先于仓库约定。设计、看板、代码或测试之间出现差异时，必须指出差异及其对应事实来源；不得静默地把设计当成已经实现，也不得仅因局部代码存在就擅自改变架构基线。

## 2. 开始工作前

开始分析、评审、修改代码、编写测试或更新文档前，按任务需要读取：

1. `agent.md`。
2. `ARCHITECTURE.md`。
3. `README.md`。
4. `openspec/config.yaml` 与当前 Change 的 proposal、specs、design、tasks。
5. `docs/go agent system - 系统看板.md`。
6. 用户指定或当前任务直接相关的代码、测试、接口和更具体的计划文档。

开始前先识别请求类型：

- **讨论、解释、评审、诊断、查看**：只读分析，不修改代码、文档、OpenSpec 或 Git 状态。
- **创建、修改、修复、重构、实施**：先确认范围与当前 Change；涉及行为、接口、持久化、跨模块边界、外部 Provider、RAG 证据行为或前后端联动时，先创建或更新 OpenSpec Change，再实施。

实施时先检查工作区和相关差异，保留用户已有的未提交修改。不得使用 `git reset --hard`、`git checkout --` 等破坏性命令覆盖用户工作；发现与任务相关的并行修改时，先理解后协作处理。

## 3. 项目最小认知模型

Go Agent System 是一个 Agent 开发平台。完整架构以 `ARCHITECTURE.md` 为准；协作者至少必须理解以下边界：

```text
平台能力：LLM、Knowledge/RAG、Ingestion、Conversation、Dialogue、Interaction、
          Agent Management、Attachment、Security
业务应用：online、agents/tender
横向技术：interfaces、infrastructure、composition、shared
```

- `app/platform/` 放置可复用的平台能力；`app/business/` 放置具体业务应用和业务 Agent。
- `ingestion` 是通用资料处理 Pipeline，政策资料只是当前验证样本。
- Knowledge/RAG 是独立的平台能力。`online` 通过 Knowledge 查询和自身 `AnswerGenerator` Port 使用检索证据，不拥有 RAG 引擎，也不直接依赖 LLM Provider。
- `agents/tender` 是业务 Agent，通过自身 Ports 使用附件、文档读取、渲染和结构化 LLM；它不是平台一级能力，也不默认依赖 Knowledge/RAG。
- Agent Management 由 Capability Catalog、Agent Call Policy、`AgentCallDispatcher` 和 Agent Runtime 组成；Agent Runtime 属于 Agent Management。
- Gateway 是自然语言控制面，负责识别、确认和受控分发；直接 HTTP Application 接口不必经过 Gateway。
- `composition` 负责依赖注入、对象组装和固定绑定，不是运行时请求中继。

## 4. 开发与分层守则

遵循 `ARCHITECTURE.md` 的完整边界；开发时至少保持以下规则：

- Interfaces 负责 HTTP、MCP、Function Calling 等协议适配、Schema、Assembler、依赖注入和异常映射，不承载复杂业务规则。
- Application Capability 负责编排用例、状态转换和跨能力协调，通过稳定契约调用其他能力。
- Domain 与 Ports 定义业务规则和所需契约，不依赖 HTTP、ORM、数据库、LLM SDK 或具体 Agent 框架。
- Infrastructure 实现 Ports 和外部系统适配，不反向编排业务用例，也不泄漏外部 SDK 类型。
- Composition Root 选择适配器、构造对象图和固定分发绑定，不放入业务规则或协议处理。
- Agent 协议适配器和业务 Agent 只能调用 Application Capability 或 Port，不得直连 Repository、数据库或 Provider SDK。
- RAG 与业务判断必须保留来源和引用；证据不足时返回受控的资料不足结果，不编造事实。
- 不因没有真实需求而预先引入复杂 Workflow、多 Agent 编排或框架抽象。

### 中文注释规则

新增或修改代码时，以下内容必须使用简洁、准确的中文注释或中文说明：

- 复杂函数、关键流程和跨模块协调。
- 非直观业务规则、安全边界、权限或数据隔离规则。
- 兼容逻辑、失败处理、临时限制和容易被误改的重要取舍。

注释优先说明“做什么”；只有存在误解风险或重要取舍时，补充“为什么”。变量赋值、简单分支和可由代码直接表达的逻辑不得逐行翻译或堆叠重复注释。注释不得包含密钥、真实业务资料、内部凭据或不应公开的运行数据。

## 5. 文档与 OpenSpec

- 架构边界发生实质变化时，更新 `ARCHITECTURE.md`；不要把进度、历史或路线图混入其中。
- 实际进度和优先级更新系统看板；README 只维护项目说明、运行方式和入口导航。
- OpenSpec 采用 delta-first：只描述当前 Change 的行为变化，不为整个历史代码库补写规格。
- 开始实施前必须阅读当前 Change 的全部已生成 artifacts；需求、设计或任务变化时，先更新 artifacts 再修改实现。
- 每项 Scenario 必须能映射到自动化测试、架构检查、前端构建或明确的人工验收证据；没有证据时不得声明完成。
- 完成的 Change 在任务全部勾选、验证通过并经人工审阅后归档；归档不替代 Git 提交。
- OpenSpec 或其他 Agent Skill 只能辅助执行，不能覆盖用户指令、架构边界和安全约束。

## 6. 测试与验收

验证范围随变更风险扩大：

- 后端行为改动至少执行相关 `pytest`；涉及跨模块或依赖边界时补充架构边界测试。
- 前端改动至少执行相关测试和 `npm run build`。
- 关键链路覆盖正常、缺失、失败、权限不足和证据不足等适用分支。
- 外部模型、Embedding、OCR 和业务系统测试使用稳定替身、固定输出或明确 skip 条件，不依赖不可控外部服务。
- 文档改动检查 Markdown 链接、旧路径、关键术语、图示调用方向和 `git diff --check`。
- Change 实施完成后执行 `openspec validate "<change-name>" --strict`。

常用检查命令：

```powershell
python -m pytest -q
ruff check app tests
python -m compileall -q app tests
Set-Location frontend
npm run build
```

未完成测试或人工验收时，只能说明已完成的验证项和未验证原因，禁止声称“已经完成”或“已经通过验收”。

## 7. 配置、安全与敏感数据

- 配置集中维护在 `app/shared/config.py`；新增配置时同步检查 `.env.example`、README 和相关说明。
- 禁止将密钥、数据库密码、真实业务凭据、真实业务资料、OCR 原始响应或运行产物提交到 Git。
- 测试和公开文档使用匿名样例、合成数据、内存数据或稳定 mock。
- 运行时文件写入 `.runtime/`；备份放在本地 `backups/`；两者及 `.tmp`、`**/ocr/output/` 都不得提交。
- 文档仅概括敏感资料，不展开真实名称、数量、类别或内容。

## 8. Git 提交与远程交付

- 只有用户明确要求提交时才创建 Git commit；只有用户明确要求推送时才执行远程 push。
- 提交标题统一使用：`分类（模块）：简洁的中文动作描述`。不使用 `feat:`、`fix:` 等 Conventional Commits 前缀。
- 常用分类：`功能`、`修复`、`测试`、`文档`、`配置`、`归档`、`破坏性变更`。模块使用项目领域或工作边界，例如 `架构`、`OpenSpec`、`LLM`、`交互`、`会话`、`附件`、`安全`。
- 一次提交只包含一个相互关联的 Change 或变更主题；不要为了提交方便混入无关文件。
- 实现型 Change 的交付顺序为：完成任务、执行验证、更新任务状态、归档 Change、检查暂存区、创建提交。用户另有指令时以用户指令为准。
- 使用显式文件路径暂存，不使用宽泛的 `git add .`。提交前必须检查：

```powershell
git status --short
git diff --stat
git diff --cached --check
git diff --cached --name-status
```

- `.tmp`、`.runtime`、`backups`、真实 SQL 备份、OCR 输出、`.env`、密钥、真实业务资料和工具运行产物不得暂存或提交；发现它们被追踪时，先停止并处理追踪状态，不把敏感内容推送到远程。
- 提交信息示例：`功能（LLM）：增加请求限流治理`、`文档（架构）：同步平台与业务分层`、`归档（OpenSpec）：完成上下文变更归档`。
