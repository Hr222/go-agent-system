# OpenSpec 使用手册与学习进程

> 用途：记录本人学习 OpenSpec 的过程、项目当前的使用方式和后续迁移约定。
>
> 当前状态：学习和渐进式接入阶段。
>
> 更新日期：2026-07-27

## 1. OpenSpec 是什么

OpenSpec 是一层位于人、AI 和代码之间的需求变更与验收契约层。它的核心目的不是增加文档数量，而是让一次功能变更在实现前后都能回答清楚：

- 为什么要做这次变更
- 这次具体改变什么行为
- 明确不改变什么
- 采用什么技术边界实现
- 什么结果才算完成
- 如何证明已经完成

官方的核心思想可以概括为：

```text
先对变更达成一致，再让 AI 实现，并用证据完成验收。
```

OpenSpec 适合已有项目。Brownfield 项目不需要先为全部历史代码补齐规格，而是每次只为即将修改的功能建立增量规格。

## 2. 官方资料

以下资料来自 OpenSpec 官方网站和官方仓库：

- 官网：https://openspec.dev/
- 核心概念：https://github.com/Fission-AI/OpenSpec/blob/main/docs/overview.md
- 已有项目接入：https://github.com/Fission-AI/OpenSpec/blob/main/docs/existing-projects.md
- 命令如何工作：https://github.com/Fission-AI/OpenSpec/blob/main/docs/how-commands-work.md
- 官方仓库：https://github.com/Fission-AI/OpenSpec

学习时以官方概念为基准，以本项目 `openspec/config.yaml`、`openspec/README.md` 和实际代码为项目约束。

## 3. 两个最重要的目录

```text
openspec/
├── specs/                 # 当前已经生效的正式能力规格
├── changes/               # 正在讨论或实施的变更
│   └── <change-name>/
│       ├── proposal.md
│       ├── specs/
│       ├── design.md
│       └── tasks.md
└── config.yaml            # 项目上下文和 OpenSpec 规则
```

### 3.1 `openspec/specs/`

这里描述系统当前已经具备、并且已经确认有效的行为，是正式规格的来源。

它应该描述：

- 用户或外部系统可以观察到的行为
- 业务约束
- 接口或状态的可观察结果
- 成功、失败、重试和证据不足等场景

它不应该直接复制：

- 阶段计划
- 架构文档
- 所有历史代码
- 还没有实现的未来设想

### 3.2 `openspec/changes/`

这里描述一次正在进行的功能变更。一个 Change 应该是一个可以独立评审、实施和验收的功能切片。

例如：

```text
tender-agent-input
```

可以负责招标文件上传和准入校验，但不应该同时负责任务生命周期、Conversation 和完整投标书生成。

## 4. Change 的四个核心 artifacts

官方推荐的基本关系是：

```text
proposal -> specs -> design -> tasks -> implementation -> archive
```

这个顺序表示上下文依赖，不是不可回退的瀑布式闸门。实现中发现范围或设计有问题时，可以回去修改前面的 artifact。

### 4.1 `proposal.md`：为什么做、做什么

回答：

- 当前问题是什么
- 预期结果是什么
- 本次范围是什么
- 明确不做什么
- 影响哪些能力、接口和模块
- 是否涉及迁移、兼容性、安全和外部服务

建议包含以下结构：

```markdown
## Why

## What Changes

## Scope

## Non-Goals

## Impact

## Compatibility and Migration
```

### 4.2 `spec.md`：系统应该表现出什么行为

规格应该描述可观察行为，而不是具体类名或框架实现。

推荐使用 Requirement 和 Scenario：

```markdown
### Requirement: The system accepts a valid tender document

系统 SHALL 接受符合准入条件的招标文件。

#### Scenario: A valid PDF is accepted

- WHEN 用户上传合法 PDF 文件
- THEN 系统接受文件并返回文件标识
- AND 返回文件名、大小和准入状态
```

必须尽量覆盖：

- 正常路径
- 参数校验失败
- 外部 Provider 失败
- 超时和重试
- 状态转换失败
- 权限或安全失败
- 证据不足
- 空结果和不可处理结果

### 4.3 `design.md`：准备怎样实现

设计文档描述实现方案和边界，通常包括：

- 模块放置
- Application、Domain、Ports、Infrastructure 的关系
- HTTP 与前端边界
- Repository、Provider 和 Adapter
- Composition Root 组装方式
- 错误映射
- 幂等性和状态转换
- 事务、迁移和回滚
- 日志、监控和安全
- 测试替身和验证方式

设计文档不是代码实现细节的逐行说明，而是让实现者和审查者知道为什么采用这条技术路径。

### 4.4 `tasks.md`：怎么完成并证明完成

任务应该是可执行的，并且有观察得到的完成条件：

```markdown
- [ ] 增加合法文件类型校验
- [ ] 增加不支持类型的 HTTP 契约测试
- [ ] 增加前端上传失败展示
- [ ] 运行后端测试和前端构建
- [ ] 完成人工验收并记录结果
```

完成任务时：

1. 先确认代码或验证已经完成。
2. 再把任务改为 `[x]`。
3. 在 `Verification evidence` 中记录命令、结果或人工验收现象。

不能只因为代码写完，就把任务全部标记为完成。

## 5. Delta-first：只写本次变化

Change 内的规格是增量规格，不是系统完整规格。

常见的增量类型：

```text
ADDED      新增行为
MODIFIED   修改已有行为
REMOVED    删除已有行为
```

例如已有 `llm-chat` 规格，下一次只是增加流式输出，则只描述流式输出相关的变化，不重新复制单轮对话、错误映射和全部架构内容。

这也是本项目采用 OpenSpec 的关键原因：可以逐步覆盖真实迭代过的能力，不需要一次性整理整个项目。

## 6. 官方工作流与本项目工作流

### 6.1 官方常见工作流

官方当前推荐：

```text
/opsx:explore        可选：先探索问题
    ->
/opsx:propose        创建 Change 并生成 artifacts
    ->
/opsx:apply          按 tasks 实现
    ->
/opsx:archive        归档并合并正式规格
```

### 6.2 本项目当前工作流

当前 Codex 环境使用 skill 形式，不要求在输入框中出现 `/opsx:*`：

```text
终端 CLI：初始化、查看、校验和归档
    +
Codex skill：探索、生成 artifacts、实现和更新 Change
```

官方概念和本地流程的映射：

| 官方操作 | 当前 Codex skill | 主要作用 |
|---|---|---|
| `/opsx:explore` | `openspec-explore` | 先理解代码和问题，不急着实现 |
| `/opsx:propose` | `openspec-propose` | 创建或完善 Change artifacts |
| `/opsx:apply` | `openspec-apply-change` | 按 tasks 实现代码 |
| `/opsx:sync` | `openspec-sync-specs` | 将变更规格同步到正式规格 |
| 编辑 Change | `openspec-update-change` | 修改范围、设计、规格或任务 |
| `/opsx:archive` | `openspec-archive-change` | 完成归档并更新正式规格 |

当前项目已经存在以下 Codex skill：

```text
.codex/skills/openspec-explore/SKILL.md
.codex/skills/openspec-propose/SKILL.md
.codex/skills/openspec-apply-change/SKILL.md
.codex/skills/openspec-update-change/SKILL.md
.codex/skills/openspec-sync-specs/SKILL.md
.codex/skills/openspec-archive-change/SKILL.md
```

在 Codex 中可以直接说：

```text
请使用 openspec-explore，先分析 tender-agent-input 的范围，不要修改代码。
```

或者：

```text
请使用 openspec-propose，为 tender-agent-input 创建完整的 OpenSpec Change。
```

## 7. CLI 常用操作

当前项目的 CLI 可以这样初始化：

```powershell
$cli = Join-Path ((npm.cmd prefix -g).Trim()) "openspec.cmd"
```

查看版本：

```powershell
& $cli --version
```

查看当前 Change：

```powershell
& $cli list --json
& $cli status --change <change-name> --json
```

创建 Change：

```powershell
& $cli new change tender-agent-input `
  --description "招标文件上传与准入校验" `
  --goal "让系统可以接受合法招标文件并返回准入结果"
```

查看 Change：

```powershell
& $cli show tender-agent-input --type change
```

严格校验：

```powershell
& $cli validate --all --strict --no-interactive
```

完成后归档：

```powershell
& $cli archive tender-agent-input
```

当前项目中，`openspec` 可能没有加入 PowerShell 的 PATH，所以使用 `$cli` 变量调用是正常的。

## 8. 什么时候必须创建 Change

以下变更通常必须先创建 Change：

- HTTP 请求或响应契约变化
- 数据库结构、持久化语义或迁移变化
- 业务规则、任务状态或错误处理变化
- 跨模块依赖、Port 或外部 Provider 变化
- RAG 引用、证据不足或规则判断行为变化
- 前后端联动、异步任务或重试机制变化
- 权限、安全、审计或敏感数据变化

以下情况通常不需要完整 Change：

- 纯样式调整
- 行为不变的局部重构
- 文档错别字
- 对已有行为的独立测试补充

简单判断：

```text
是否改变用户、接口、业务规则、模块边界或验收方式？
是 -> 创建 Change
否 -> 可以直接处理
```

## 9. 如何控制 Change 范围

一个 Change 应该满足：

- 可以在一次迭代中完成
- 有明确的用户或系统结果
- 有明确的非目标
- 可以单独测试和验收
- 不需要把整个阶段计划放进去

不推荐：

```text
tender-agent-phase-3
```

更推荐拆成：

```text
tender-agent-input
task-management
tender-skeleton
conversation-context
```

其中每个 Change 只覆盖一个可以独立评审的功能切片。

## 10. 如何处理现有阶段文档

现有阶段文档不需要一次性全文迁移。官方 Brownfield 建议是：把原文档当作探索和提取需求的背景材料。

当前项目的处理方式：

| 旧内容 | 后续处理 |
|---|---|
| 阶段背景和长期目标 | 暂时保留在原阶段文档或长期架构说明中 |
| 已开始的具体功能 | 建立对应 Change |
| 尚未开始的计划 | 暂不创建正式规格，开始时再建立 Change |
| 当前实现进度 | 记录在 Change 的 tasks 和验证证据中 |
| 长期架构约束 | 保留在 `ARCHITECTURE.md`、`agent.md` 等文件中 |
| 已完成 Change | 归档后进入 `openspec/specs/` |

在过渡期间：

```text
旧阶段文档 = 历史和背景
OpenSpec Change = 当前实施工作
openspec/specs = 已生效行为
```

不要在满足迁移条件前删除三份阶段文档。

## 11. 现有 Change 学习案例

当前项目已有：

```text
openspec/changes/complete-llm-chat-acceptance/
```

它只覆盖 F1-A 的独立 LLM 单轮对话验收，不代表 F1 或 Tender Agent 整体完成。

案例中的边界：

- 有真实的 `POST /api/v1/llm/chat` 请求和响应契约
- 有空消息、超长消息、服务未配置、上游失败和空响应场景
- 前端有加载、成功、错误和重试状态
- 不包含上下文记忆、会话持久化、工具调用、RAG 和完整 Agent
- Application 只依赖稳定的 LLM Port
- 测试和人工验收证据记录在 `tasks.md`

阅读这个 Change 时，重点观察：

1. `proposal.md` 如何限制范围。
2. `spec.md` 如何把行为写成 Scenario。
3. `design.md` 如何保持架构边界。
4. `tasks.md` 如何记录实现和证据。

## 12. 第一次实际练习

推荐使用 `tender-agent-input` 作为第一个真实练习，但先只做探索和规划。

### 第一步：探索

```text
请使用 openspec-explore，结合当前代码、架构文档和旧阶段文档，
分析 tender-agent-input 的真实范围。

只覆盖招标文件上传、文件校验和准入结果，
不要包含 Task Management、Conversation、F2 和完整投标书生成。

先只做分析，不创建文件，不修改代码。
```

### 第二步：确认范围

重点确认：

- 是否真的需要创建任务
- 文件存储和元数据由哪个模块负责
- 文件是否进入知识库
- HTTP 请求和响应是什么
- 失败后是否支持重试
- 前端需要展示哪些状态

### 第三步：创建 Change

确认范围后再使用 `openspec-propose`，生成 proposal、specs、design 和 tasks。

### 第四步：审阅 artifacts

重点检查：

- 是否混入 Task Management
- 是否把未来规划写成当前需求
- Scenario 是否包含失败分支
- tasks 是否有明确完成条件
- design 是否符合现有架构

### 第五步：实现和验证

使用 `openspec-apply-change` 实现任务，完成后执行：

```powershell
& $cli validate --all --strict --no-interactive
```

只有代码、测试、构建和人工验收都完成后，才考虑归档。

## 13. 常见误区

### 误区一：把 OpenSpec 当成项目总计划

OpenSpec 更适合管理具体功能变更。长期路线、技术债和调研笔记不需要全部变成 Change。

### 误区二：先为整个项目补规格

Brownfield 项目应该采用增量方式。只为当前要改变的能力建立规格。

### 误区三：`tasks.md` 全部打勾就算完成

任务必须有测试、构建、架构检查或人工验收证据。

### 误区四：Scenario 只写正常路径

错误、超时、重试、无数据、证据不足和外部服务失败同样属于功能契约。

### 误区五：设计变了但不更新 artifacts

如果实现中发现设计、目标或范围变化，应先更新对应 artifact，再继续代码实现。

### 误区六：把架构文档复制到 specs

`specs` 描述可观察行为，`ARCHITECTURE.md` 描述长期模块和依赖约束，两者职责不同。

### 误区七：为了看到 `/opsx:*` 命令而反复配置

Codex 使用 `.codex/skills/openspec-*` 形式。可以直接使用 `OpenSpec Explore` 等 skill，不要求输入框出现官方 slash command。

## 14. 学习进程记录

### 已完成

- [x] 理解 OpenSpec 是需求变更和验收契约层
- [x] 理解 `openspec/specs/` 和 `openspec/changes/` 的区别
- [x] 理解 Change 是一个独立、可评审、可验证的功能切片
- [x] 理解 proposal、spec、design、tasks 的职责
- [x] 理解 Brownfield 项目采用 delta-first，不需要一次性补齐全部规格
- [x] 理解官方 slash command 与 Codex skill 的区别
- [x] 在 Codex 中发现并使用 OpenSpec skills
- [x] 阅读项目现有的 `complete-llm-chat-acceptance`

### 进行中

- [ ] 使用 `openspec-explore` 分析第一个实际功能
- [ ] 使用 `openspec-propose` 创建第一个学习用 Change
- [ ] 人工审阅 proposal、specs、design 和 tasks

### 待完成

- [ ] 使用 `openspec-apply-change` 完成一个真实 Change
- [ ] 记录完整测试、构建和人工验收证据
- [ ] 使用 `openspec-archive-change` 归档一次 Change
- [ ] 观察归档后 `openspec/specs/` 的变化
- [ ] 按 Change 逐步替代旧阶段进度文档
- [ ] 满足迁移桥接条件后，再单独删除旧阶段文档

## 15. 一句话记忆

```text
探索问题，明确范围；
写出行为，说明设计；
拆成任务，边做边证；
完成归档，规格生效。
```
