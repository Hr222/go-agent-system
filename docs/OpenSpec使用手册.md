# OpenSpec 使用手册与学习进程

> 用途：记录本人学习 OpenSpec 的过程、项目当前的使用方式和后续迁移约定。
>
> 当前状态：学习和渐进式接入阶段。
>
> 更新日期：2026-07-29

## 目录与分类

这份手册按“先理解，再操作，最后复盘”的顺序组织。可以按当前目标直接进入对应分类：

| 分类 | 章节 | 适合解决的问题 |
|---|---|---|
| 基础概念 | [1. OpenSpec 是什么](#1-openspec-是什么)、[2. 官方资料](#2-官方资料)、[3. 两个最重要的目录](#3-两个最重要的目录) | OpenSpec 管什么，正式规格和 Change 放在哪里 |
| Change 产物 | [4. Change 的四个核心 artifacts](#4-change-的四个核心-artifacts)、[4.2 Specs 的章节写法](#42-specmd系统应该表现出什么行为)、[4.3 Design 的章节写法](#43-designmd准备怎样实现)、[4.4 Tasks 的章节写法](#44-tasksmd怎么完成并证明完成)、[5. Delta-first](#5-delta-first只写本次变化) | Proposal、Specs、Design、Tasks 分别写什么，以及它们如何衔接 |
| 工作流、同步与 CLI | [6. 官方工作流与本项目工作流](#6-官方工作流与本项目工作流)、[6.3 Apply 阶段：按任务实现和暂停](#63-apply-阶段按任务实现和暂停)、[6.4 Sync 与 Archive：让已完成行为成为正式规格](#64-sync-与-archive让已完成行为成为正式规格)、[7. CLI 常用操作](#7-cli-常用操作)、[7.2 CLI 初始化与基础状态查询](#72-cli-初始化与基础状态查询)、[7.3 Change 与 Apply 操作](#73-change-与-apply-操作) | 如何创建 Change、获取指令、按任务实现、同步正式规格、归档和校验 |
| 需求边界与项目实践 | [8. 什么时候必须创建 Change](#8-什么时候必须创建-change)、[9. 如何控制 Change 范围](#9-如何控制-change-范围)、[10. 如何处理现有阶段文档](#10-如何处理现有阶段文档)、[11. 现有 Change 学习案例](#11-现有-change-学习案例)、[12. 第一次实际练习](#12-第一次实际练习) | 如何判断是否需要 Change，如何拆分和落地到当前项目 |
| 排错与学习记录 | [13. 常见误区](#13-常见误区)、[14. 学习进程记录](#14-学习进程记录)、[15. 一句话记忆](#15-一句话记忆) | 避免常见误用，记录当前学习进度 |

Change 产物的阅读顺序不是单线流程，而是：

```text
proposal
   ├──> specs
   └──> design
          └──> tasks（等待 specs 和 design 都完成）
                    └──> implementation → sync specs → archive
```

当前学习分支已完成 `llm-chat-streaming` 及其两次体验迭代：`improve-chat-stream-visibility` 和 `add-chat-stream-pacing`。三份 Change 的代码、测试、构建和浏览器验收均已完成，下一步是按顺序同步 `llm-chat` 主规格并归档。

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

一个 Change 的依赖关系是：

```text
             ┌──> specs ──┐
proposal ────┤             ├──> tasks ──> implementation ──> sync specs ──> archive
             └──> design ──┘
```

`proposal` 完成后，`specs` 和 `design` 都可以开始；`tasks` 必须等两者都完成。这个关系不是不可回退的瀑布流程：实现中发现范围或设计有问题时，应回去修改对应 artifact，再继续后续工作。

### 4.1 `proposal.md`：为什么做、做什么

Proposal 是一次变更的立项说明，不是技术设计，也不是任务清单。它主要回答：

- 当前问题和改动原因是什么（Why）
- 预期改变哪些行为（What Changes）
- 涉及新增能力还是修改已有能力（Capabilities）
- 哪些接口、模块、前端、测试、数据和兼容性会受到影响（Impact）

当前 `spec-driven` Schema 的标准结构是：

```markdown
## Why

## What Changes

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact
```

#### 4.1.1 `Why`

用一到两句话说明现状问题、机会和为什么现在要做。只讲事实和目标，不写技术方案。

#### 4.1.2 `What Changes`

列出本次变更会带来的行为变化、范围和非目标。当前 CLI 模板没有单独的 `Scope` 或 `Non-Goals` 标题，项目要求的范围和非目标应写在这一节中。

可以写：

- 新增或修改什么用户可观察行为
- 哪些流程、失败分支和边界需要明确
- 明确不引入哪些相关但不属于本次的能力
- 如果改变现有契约，使用 `**BREAKING**` 标明兼容性风险

不要在这里展开具体类、函数、目录或框架选型；实现方案放到 `design.md`。

#### 4.1.3 `Capabilities`

`Capabilities` 用来把 Proposal 连接到后续的规格文件，不是影响范围分类。

```text
Capabilities
├── New Capabilities       新增能力，后续创建新的 specs/<name>/spec.md
└── Modified Capabilities  修改已有能力，后续为已有规格编写增量 spec
```

- `New Capabilities`：`openspec/specs/` 中还没有对应正式规格的能力。
- `Modified Capabilities`：已有正式规格，但本次会改变其 Requirement 或可观察行为的能力。
- 当前 Schema 没有单独的 `Impact Capabilities` 或 `Removed Capabilities`。删除已有行为时，放在 `Modified Capabilities` 中说明，并在 delta spec 中明确 `REMOVED` 的 Requirement。

例如已有 `llm-chat` 规格，本次只增加流式输出：

```markdown
### New Capabilities

无。

### Modified Capabilities

- `llm-chat`：修改单轮对话响应契约，使回答可以增量返回和展示。
```

#### 4.1.4 `Impact`

`Impact` 是和 `Capabilities` 平级的章节，说明变更会波及哪些地方，而不是说明新增了哪项能力：

```markdown
## Impact

- 后端接口：请求、响应和错误映射
- 后端模块：Application、Port、Adapter 和 HTTP 路由
- 前端模块：API 调用、页面状态和错误展示
- 测试与验收：契约测试、架构检查、构建和人工验收
- 数据与迁移：数据库、持久化和迁移是否变化
- 兼容性：现有客户端、外部 Provider 和部署配置是否受影响
```

Proposal 可以提到高层影响和待确定的兼容策略，但不要在这里决定 SSE、WebSocket、具体 SDK 方法等实现细节。

Proposal 的正文默认使用中文；`Requirement`、`Scenario`、`WHEN`、`THEN`、`AND`、`MUST` 等 OpenSpec 结构标记以及代码、接口和库名可以保留英文。

### 4.2 `spec.md`：系统应该表现出什么行为

`spec.md` 是系统对外行为的正式契约，不是问题清单，也不是技术实现说明。它回答：

```text
在什么条件下，系统必须表现出什么结果？
```

本项目的规格使用两层结构：

```text
Requirement
    规定一条必须满足的系统行为

Scenario
    用具体场景说明这条行为如何被验证
```

本小节索引：

- [4.2.1 Specs 的职责](#421-specs的职责)
- [4.2.2 Requirement 的写法](#422-requirement的写法)
- [4.2.3 Scenario 的写法](#423-scenario的写法)
- [4.2.4 MODIFIED 与 ADDED](#424-modified与-added)
- [4.2.5 Specs 的覆盖范围](#425-specs的覆盖范围)
- [4.2.6 Specs 不写什么](#426-specs不写什么)

#### 4.2.1 Specs 的职责

`specs` 描述用户或外部系统能够观察到的行为。它不是单纯记录“可能存在的问题”，而是规定系统必须如何处理正常、异常和边界场景。

例如流式 Chat 需要明确：

- 成功时如何返回增量内容
- 输入错误时返回什么结果
- Provider 失败时如何表达
- 用户取消时如何处理已收到的文本
- 旧 JSON 接口必须保持什么行为
- 前端应该展示哪些请求状态

每个 Scenario 都应该能够转换成测试用例或人工验收步骤，但 `spec.md` 本身不是测试代码。

#### 4.2.2 Requirement 的写法

`Requirement` 是一条完整的规范要求，描述系统必须具备的能力或必须遵守的规则。

标题使用自然中文，正文使用明确的规范性表达：

```markdown
### Requirement: 系统支持流式单轮对话

系统必须（MUST）通过流式接口按模型生成顺序返回单轮回答内容。
```

推荐使用：

- 系统必须（MUST）……
- 系统不得（MUST NOT）……
- 系统必须返回……
- 系统必须拒绝……
- 系统必须保留……

避免使用含义不明确的词：

```markdown
- 系统应该尽量支持流式输出。
- 系统可能返回错误。
- 系统适当处理超时。
```

这些表达无法作为稳定的验收标准。应改成明确的状态、响应、事件或用户可观察结果。

#### 4.2.3 Scenario 的写法

每个 Requirement 至少包含一个 Scenario。Scenario 必须使用四级标题，不能写成三级标题：

```markdown
#### Scenario: 有效消息返回流式响应

- **WHEN** 客户端提交合法消息
- **THEN** 系统返回 `text/event-stream`
- **AND** 系统按顺序发送增量内容
- **AND** 正常结束时发送完成事件
```

固定结构是：

```text
WHEN    触发条件或前置状态
THEN    首要结果
AND     其他必须同时成立的结果
```

一个 Scenario 应该描述一个可以独立验证的场景。不要把多个互不相关的输入和结果塞进同一个场景。

适用时应覆盖：

- 正常路径
- 参数校验失败
- 外部 Provider 失败
- 超时和重试
- 用户取消或客户端断开
- 状态转换失败
- 权限或安全失败
- 证据不足
- 空结果和不可处理结果

不是所有项目都需要覆盖全部类型，只需要覆盖本次 Change 相关的分支。知识库或业务判断涉及 RAG 时，还必须定义来源追踪，以及证据不足时系统如何提示或拒绝判断。

#### 4.2.4 `MODIFIED` 与 `ADDED`

Change 内的 specs 是增量规格。选择操作类型时按以下规则判断：

```text
ADDED      新增一条过去不存在的 Requirement
MODIFIED   修改已有 Requirement 的行为
REMOVED    删除已有 Requirement
RENAMED    只修改 Requirement 名称
```

如果已有 `openspec/specs/llm-chat/spec.md`，本次只是给它增加流式行为，应创建：

```text
openspec/changes/llm-chat-streaming/specs/llm-chat/spec.md
```

并使用：

```markdown
## MODIFIED Requirements
```

`MODIFIED` 有一个重要规则：必须复制原 Requirement 的完整内容，再修改它。不能只写新增的几行，否则归档时可能丢失原有场景。

如果只是增加一项与已有 Requirement 独立的新行为，才使用：

```markdown
## ADDED Requirements
```

`REMOVED Requirements` 必须额外说明 `Reason` 和 `Migration`。

#### 4.2.5 Specs 的覆盖范围

Specs 应覆盖本次 Change 中真正改变的外部行为：

- HTTP 请求、响应和状态码
- SSE 或其他外部事件顺序和字段
- 用户界面状态和交互结果
- 失败、取消、超时和重试行为
- 外部 Provider 的可观察失败映射
- 数据、权限、安全和审计结果
- 旧接口的兼容性要求

可以用下面的问题检查一条 Requirement 是否完整：

```text
谁触发？
触发条件是什么？
系统返回什么？
失败时返回什么？
用户或外部系统能观察到什么？
如何测试或验收？
```

#### 4.2.6 Specs 不写什么

Specs 不应写成以下内容：

- Python 类名、TypeScript 函数名或具体文件路径
- LangChain、FastAPI、React Hook 等内部实现选择
- Application、Port、Adapter 的内部调用顺序
- 逐行实现步骤
- 尚未确定的技术方案
- 与本次 Change 无关的现有系统介绍

这些内容分别属于 `design.md`、`tasks.md` 或长期架构文档。

四个 artifact 的核心区别是：

```text
proposal.md  为什么改、改什么
design.md    准备用什么方案改、为什么这样改
spec.md      改完后系统必须表现成什么样
tasks.md     分哪些步骤实现，以及如何证明完成
```

### 4.3 `design.md`：准备怎样实现

设计文档回答“准备怎样实现，以及为什么这样实现”。它建立在 proposal 的范围和影响之上，重点描述技术方案、模块边界、关键取舍、风险和迁移方式。

本小节索引：

- [4.3.1 `Context`：背景和约束](#431-context背景和约束)
- [4.3.2 `Goals / Non-Goals`：目标和非目标](#432-goals--non-goals目标和非目标)
- [4.3.3 `Decisions`：技术决策](#433-decisions技术决策)
- [4.3.4 `Risks / Trade-offs`：风险和代价](#434-risks--trade-offs风险和代价)
- [4.3.5 `Migration Plan`：迁移和回滚](#435-migration-plan迁移和回滚)
- [4.3.6 `Open Questions`：待确认问题](#436-open-questions待确认问题)
- [4.3.7 Design 的总体写法](#437-design的总体写法)

设计文档不是代码实现细节的逐行说明，也不是 tasks 的提前展开。它需要让实现者和审查者理解技术路径，以及这条路径对旧功能、其他模块和生产环境的影响。

#### 4.3.1 `Context`：背景和约束

`Context` 描述当前事实、问题背景和必须遵守的约束，不在这里提前宣布解决方案。

适合写：

- 当前系统如何工作
- 本次变更为什么需要技术设计
- 涉及哪些模块和外部系统
- 必须遵守哪些架构、兼容性或安全约束

示例：

```markdown
当前接口通过同步调用等待 LLM 完整返回，前端只能在请求结束后展示回答。

本次变更涉及 HTTP、Application、LLM Port、Provider Adapter 和前端 Chat 状态，
因此需要先明确跨模块的流式设计。
```

不要在 `Context` 中直接写具体实现：

```markdown
当前需要新增 StreamingChatApplication。
```

这属于 `Decisions`，因为它已经提出了实现方案。

#### 4.3.2 `Goals / Non-Goals`：目标和非目标

`Goals` 写设计完成后系统应该具备的结果，回答“这次设计要达成什么”。推荐使用“支持、能够、保留、确保、避免”等动词。

```markdown
**Goals:**

- 新增流式 HTTP 接口。
- 用户能够逐步看到模型输出。
- 保留旧 JSON 接口行为。
- 用户取消后能够释放上游请求资源。
- 流式请求能够被监控和统计。
```

`Non-Goals` 写明确不做的事情，用来阻止 Change 范围继续扩大。

```markdown
**Non-Goals:**

- 不引入会话历史。
- 不修改数据库。
- 不引入 RAG、工具调用或 Agent 编排。
- 不实现自动重试。
```

目标应描述结果，不应写成具体文件或函数任务：

```markdown
- 新增一个 `useChatStream` Hook。
- 修改 `llm.py` 路由。
```

这类内容可以在 `Decisions` 中说明归属，在 `tasks.md` 中拆成实施任务。

#### 4.3.3 `Decisions`：技术决策

每个重要决策单独编号，并尽量包含三部分：

```text
选择什么
为什么选择
为什么不选择其他方案
```

示例：

```markdown
### 1. 使用独立的流式 HTTP 入口

新增 `POST /api/v1/llm/chat/stream`，保留原有
`POST /api/v1/llm/chat`。

这样可以保证旧客户端继续使用原 JSON 契约。相比直接修改原接口，
新增入口能够降低兼容性风险，并允许后续逐步迁移客户端。
```

涉及多个模块时，可以补充依赖关系：

```text
HTTP Route
    -> Application
    -> Port
    -> Provider Adapter
    -> LLM Provider
```

常见的技术决策包括：

- HTTP 协议和接口路径
- 模块职责和依赖方向
- 数据结构和状态流转
- 错误映射和取消传播
- Provider、Repository 和 Adapter 的边界
- Composition Root 的组装方式
- 资源生命周期、并发和超时
- 日志、指标、安全和敏感数据处理

一个小节只表达一个完整判断，不要把多个互相独立的选择堆在一个大段落中。

#### 4.3.4 `Risks / Trade-offs`：风险和代价

这里不只是列出“可能有风险”，还要说明风险产生的原因和应对措施。推荐使用：

```text
风险或代价 -> 应对措施
```

例如：

```markdown
- [风险] 反向代理可能缓冲 SSE 内容，导致用户无法及时看到增量输出。
  → [应对] 关闭代理缓冲，增加心跳，并进行代理后的首 Token 验收。
```

`Trade-off` 要说明技术选择带来的代价，而不是假设方案没有缺点：

```markdown
- SSE 适合服务端持续推送，但不适合双向交互。
- `ReadableStream` 能够处理分块响应，但会对现有 Axios 统一请求规则增加受控例外。
```

#### 4.3.5 `Migration Plan`：迁移和回滚

`Migration Plan` 描述如何从旧系统逐步进入新状态，至少要覆盖：

1. 先实现什么。
2. 如何验证。
3. 如何上线。
4. 旧功能如何继续工作。
5. 出问题如何回滚。
6. 是否需要数据库迁移。

示例：

```markdown
1. 增加流式 Port 和 Provider Adapter。
2. 增加新的 SSE 路由和测试。
3. 增加前端流式 Hook。
4. 通过新接口进行联调。
5. 旧 JSON 接口继续保留。
6. 流式功能异常时，前端回退到旧 JSON 接口。
7. 本次不需要数据库迁移。
```

如果没有数据库、持久化或迁移影响，也要明确写“无”，不要留下歧义。

#### 4.3.6 `Open Questions`：待确认问题

这里只记录当前尚未确定、并且可能影响实现或上线的问题。

好的问题应该具体：

```markdown
- Provider 是否能在流结束时返回完整 Token 用量？
- 生产环境允许的最大并发流数量是多少？
- 反向代理的空闲超时时间是多少？
- 是否需要配置开关控制流式入口？
```

已经确定的内容不应继续写成 Open Question。例如已经决定使用 SSE，就不要再写“是否使用 SSE”。

#### 4.3.7 Design 的总体写法

可以用下面的关系理解各个章节：

| 章节 | 核心问题 | 写作重点 |
|---|---|---|
| `Context` | 现在是什么情况？ | 当前事实、背景和约束 |
| `Goals` | 这次要达到什么结果？ | 用户或系统最终获得的能力 |
| `Non-Goals` | 明确不做什么？ | 范围边界和排除项 |
| `Decisions` | 准备用什么方案？ | 选择、理由和替代方案 |
| `Risks / Trade-offs` | 有什么风险和代价？ | 风险原因、影响和应对 |
| `Migration Plan` | 如何上线和回滚？ | 实施顺序、兼容和回退 |
| `Open Questions` | 还有什么没确定？ | 需要后续验证的具体问题 |

设计文档应遵循以下顺序：

```text
先说明背景和边界
  -> 再说明目标和非目标
  -> 然后做出技术决策
  -> 接着暴露风险和代价
  -> 最后说明迁移、回滚和待确认问题
```

一次跨模块变更还应检查以下内容是否覆盖：

- 前端和后端边界
- Application、Ports、Adapters 和 Composition Root
- HTTP 契约和错误映射
- 状态流转、取消、超时和幂等性
- Provider、数据库或其他外部依赖
- 日志、指标、安全和敏感数据
- 测试、发布、回滚和数据迁移

`design.md`、`spec.md` 和 `tasks.md` 的职责不要混淆：

```text
proposal.md  说明为什么改、改什么
design.md    说明怎么改、为什么这样改
specs        说明外部行为必须满足什么要求
tasks.md     说明分几步实施，以及如何证明完成
```

### 4.4 `tasks.md`：怎么完成并证明完成

`tasks.md` 是实现和验证清单。它把 `specs` 中必须满足的行为，以及 `design` 中确定的技术路径，拆成可以执行、验证和追踪的任务。

它不是需求说明，也不是单独的验收标准：

```text
specs   定义系统必须满足什么行为
tasks   列出实现这些行为并证明完成的工作
```

本小节索引：

- [4.4.1 Tasks 的职责](#441-tasks的职责)
- [4.4.2 固定格式](#442-固定格式)
- [4.4.3 单个任务的写法](#443-单个任务的写法)
- [4.4.4 任务拆分原则](#444-任务拆分原则)
- [4.4.5 任务依赖和顺序](#445-任务依赖和顺序)
- [4.4.6 实现任务与验收任务](#446-实现任务与验收任务)
- [4.4.7 规格追溯和完成证据](#447-规格追溯和完成证据)
- [4.4.8 本次 Change 的任务分组](#448-本次-change的任务分组)

#### 4.4.1 Tasks 的职责

Tasks 的核心是：

```text
把“系统必须达到的结果”拆成“可以独立完成和验证的工作”。
```

它回答：

- 要先做哪些工作
- 每项工作负责什么范围
- 哪些工作依赖其他工作
- 什么现象可以证明任务完成
- 哪些测试、构建或人工验收必须执行

一个任务不等于一个 Requirement，也不等于一个 Scenario：

```text
一个 Requirement 可能需要多个实现、测试和验收任务
一个任务也可能同时支持多个 Scenario
```

因此不能简单地把 4 个 Requirement 直接写成 4 个任务。

#### 4.4.2 固定格式

OpenSpec 的任务格式必须保持可解析：

```markdown
## 1. 后端流式应用能力

- [ ] 1.1 增加流式 LLM Port 和 Application 契约
- [ ] 1.2 增加 Provider 异步流式适配
```

格式规则：

- 任务组使用 `## 1.`、`## 2.` 等编号标题。
- 每一项任务必须使用 `- [ ]` 开始。
- 子任务使用 `1.1`、`1.2`、`2.1` 等编号。
- `[ ]` 表示未完成，`[x]` 表示已完成。
- 不要用普通无序列表替代任务复选框，否则 apply 阶段无法可靠追踪。

获取当前 Schema 的任务格式和约束：

```powershell
openspec instructions tasks --change <change-name> --json
```

#### 4.4.3 单个任务的写法

一个任务推荐使用下面的结构：

```text
动作 + 目标 + 完成条件 + 规格追溯
```

例如：

```markdown
- [ ] 2.2 实现 `meta`、`delta`、`complete`、`error` 和 `heartbeat` 事件的序列化；完成条件：合法请求能够按约定顺序发送事件，`delta` 内容保持生成顺序。（对应 Scenario：有效消息建立流式响应）
```

这项任务包含四类信息：

- 动作：实现事件序列化
- 目标：支持规定的五类事件
- 完成条件：顺序正确、内容顺序正确
- 追溯关系：对应哪个 Scenario

避免使用无法验收的描述：

```markdown
- [ ] 完善流式功能
- [ ] 处理相关问题
- [ ] 优化前后端交互
```

应改成可观察的结果：

```markdown
- [ ] 增加流式 HTTP 契约测试；完成条件：覆盖事件顺序、首内容前错误、部分内容后错误和取消场景。
```

#### 4.4.4 任务拆分原则

一个任务通常应满足：

- 可以在一次工作会话中完成
- 具有清晰的代码、测试或运行环境边界
- 可以独立测试或检查
- 有明确的完成条件
- 不需要同时处理多个不相关的问题

需要拆分的信号包括：

- 任务同时涉及后端、前端和部署环境
- 完成条件包含多个相互独立的结果
- 任务无法在一次正常工作会话中完成
- 失败后无法判断到底是哪一部分没有完成

但也不要过度拆分。以下内容通常可以属于同一个任务：

```text
实现一个内部数据结构及其对应的单元测试
增加一个接口及其请求校验测试
增加一个前端 Hook 及其状态转换测试
```

拆分的依据不是代码文件数量，而是工作是否可以独立实施和验证。

#### 4.4.5 任务依赖和顺序

任务应按照依赖关系和风险顺序排列，而不是按照想到的先后排列。

典型顺序是：

```text
后端核心能力
    -> HTTP 接口
        -> 资源治理和错误处理
            -> 前端交互
                -> 自动化测试和架构检查
                    -> 运行环境和最终验收
```

跨模块变更通常应分组覆盖：

- 后端 Application、Port 和 Adapter
- HTTP 接口和错误映射
- 取消、超时、并发和资源释放
- 前端 API、Hook 和页面状态
- 后端、前端和架构边界测试
- 代理、日志、指标和人工验收

如果一个任务依赖前一个任务，编号顺序应体现这种关系。例如前端 Hook 依赖流式 API 契约，集成测试依赖前后端实现都完成。

#### 4.4.6 实现任务与验收任务

Tasks 同时包含实现和验证，不是只写代码任务：

```text
实现任务：增加流式 Port、SSE 路由和前端 Hook
测试任务：增加 Application、HTTP 和前端测试
验收任务：验证代理、取消、并发、日志和敏感信息
```

实现任务的完成条件可以是代码行为和自动化测试结果；验收任务的完成条件可以是：

- 测试命令成功
- 前端构建成功
- 浏览器中观察到增量输出
- 代理转发后仍能看到首 Token
- 客户端取消后 Provider 停止消费
- 日志中没有 Prompt、增量内容和 API Key

Specs 是“验收规则”，Tasks 是“实现加验收清单”。两者不能互相替代。

#### 4.4.7 规格追溯和完成证据

每项任务尽量关联对应的 Requirement 或 Scenario，形成下面的追溯关系：

```text
Requirement / Scenario
        -> Task
            -> Code / Test / Configuration
                -> Verification Evidence
```

任务完成时：

1. 先完成代码、配置或验证工作。
2. 执行对应测试、构建或人工验收。
3. 记录命令、结果或观察现象。
4. 确认没有未解决的失败后，再把 `[ ]` 改为 `[x]`。

验证证据可以包括：

```text
pytest 测试通过
npm run build 通过
openspec validate 通过
浏览器人工验收成功
代理后的首 Token 验证成功
```

不能因为代码已经写完，就把所有任务一次性标记为完成。没有验证证据的任务不得标记为 `[x]`。

#### 4.4.8 本次 Change 的任务分组

`llm-chat-streaming` 当前按照以下边界拆分 tasks：

```text
1. 后端流式应用能力
2. 流式 HTTP 接口
3. 取消、超时和资源治理
4. 前端流式交互
5. 测试和架构验证
6. 运行环境和最终验收
```

这 6 个任务组下共有 21 个任务。数量不是固定规则，而是本次端到端变更按照后端、前端、运行环境和验收边界拆分后的结果。

任务组和 Requirement 的关系不是一对一：一个 Requirement 可能跨越多个任务组，一个任务也可能同时验证多个 Scenario。

完成任务后，使用 OpenSpec 状态检查确认进度：

```powershell
openspec status --change <change-name> --json
openspec list --json
```

`status` 主要查看 Change 和 artifacts 是否完整，`list --json` 会直接显示任务进度，例如：

```json
{
  "name": "llm-chat-streaming",
  "completedTasks": 1,
  "totalTasks": 21,
  "status": "in-progress"
}
```

完成全部任务并验证 Change 后，才进入归档流程。

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

同一能力可以连续产生多个 Change。后续 Change 仍然只描述相对当时主规格的变化；当这一组迭代完成时，再按发生顺序将它们同步回主规格，而不是把多个 delta spec 直接拼接。

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
/opsx:sync           将已验收的 delta spec 合并到正式规格
    ->
/opsx:archive        归档完成的 Change
```

### 6.2 本项目当前工作流

当前项目有两个入口，职责不同：

```text
CLI：创建 Change 骨架、查看状态、获取 artifact 指令、校验和执行归档
  +
Codex：探索需求、协助编写 artifacts、实现 tasks、合并 delta spec 和更新 Change
```

截图中看到的 `/opsx:*` 是 Codex 提供的 prompts/skills 入口。它们可以在已有 Change 上继续工作，但不是创建空 Change 的唯一方式；创建空 Change 时，CLI 的 `openspec new change` 最清晰。

官方概念和本地流程的映射：

| 官方操作 | 当前 Codex skill | 主要作用 |
|---|---|---|
| `/opsx:explore` | `openspec-explore` | 先理解代码和问题，不急着实现 |
| `/opsx:propose` | `openspec-propose` | 创建 Change 并一次性生成全部 artifacts；学习时不建议直接使用 |
| `/opsx:apply` | `openspec-apply-change` | 按 tasks 实现代码 |
| `/opsx:sync` | `openspec-sync-specs` | 将变更规格同步到正式规格 |
| `/opsx:update` | `openspec-update-change` | 修改已有 Change 的范围、设计、规格或任务 |
| `/opsx:archive` | `openspec-archive-change` | 检查完成状态并归档 Change 工件 |

想逐步学习时，推荐使用：

```text
CLI 创建空 Change
  -> CLI status / instructions
  -> Codex 或编辑器只写 proposal
  -> 审核后再写 specs 和 design
  -> specs + design 完成后写 tasks
  -> 最后才 apply
```

不要把 `/opsx:propose` 和“只创建 Change”混为一谈：`propose` 会同时生成完整规划材料；它适合已经明确需求、希望快速完成规划的场景。

### 6.3 Apply 阶段：按任务实现和暂停

本小节索引：

- [6.3.1 Apply 阶段的文档依据](#631-apply-阶段的文档依据)
- [6.3.2 Skill 与 CLI 的分工](#632-skill-与-cli-的分工)
- [6.3.3 单任务执行流程](#633-单任务执行流程)
- [6.3.4 实现中的暂停与回退](#634-实现中的暂停与回退)

#### 6.3.1 Apply 阶段的文档依据

当 `proposal`、`specs`、`design` 和 `tasks` 都完成后，才进入实现阶段。实现阶段的直接执行清单是 `tasks.md`，但实现者必须同时参考：

```text
proposal.md  约束为什么做、范围和非目标
specs        约束系统必须表现出的行为
design.md    约束技术方案、模块边界和关键取舍
tasks.md     列出本次要实施和验证的任务
```

#### 6.3.2 Skill 与 CLI 的分工

在 Codex 中使用 `openspec-apply-change` Skill：

```text
请使用 openspec-apply-change，实现 llm-chat-streaming。
先只执行任务 1.1，完成代码和测试后暂停。
```

这里要区分 Skill 和 CLI 指令：

- `openspec-apply-change` 是 Codex 的工作流 Skill，负责读取 Change 上下文、实现任务、运行验证并更新任务状态。
- `openspec instructions apply --change <change-name> --json` 是 OpenSpec CLI 指令，用来输出 apply 阶段的上下文、任务清单和当前进度。
- `openspec list --json` 是进度查询指令，不负责实现代码。

#### 6.3.3 单任务执行流程

一次受控的单任务实现流程是：

```text
确认 Change 和当前进度
    -> 读取 proposal、specs、design、tasks
    -> 指定只执行一个任务
    -> 修改代码和对应测试
    -> 运行相关测试、静态检查和必要的规格校验
    -> 验证通过后把该任务从 [ ] 改为 [x]
    -> 用 openspec list --json 确认进度
    -> 按用户要求暂停，不能自动执行后续任务
```

例如本次 `llm-chat-streaming` 的任务 1.1 完成后，状态应为 `1/21`，而不是把同一组中的 1.2、1.3 或其他任务一并标记。只有在用户明确允许继续时，才进入下一个任务。

#### 6.3.4 实现中的暂停与回退

如果实现过程中发现 `specs` 或 `design` 与实际代码冲突，应暂停实现，先更新对应 artifact 并重新审核；不能为了让代码通过而擅自改变已确认的行为契约。

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

### 6.4 Sync 与 Archive：让已完成行为成为正式规格

本小节索引：

- [6.4.1 正式规格、delta spec 与归档的分工](#641-正式规格delta-spec-与归档的分工)
- [6.4.2 连续迭代同一能力时的同步顺序](#642-连续迭代同一能力时的同步顺序)
- [6.4.3 在 Codex 中如何请求同步和归档](#643-在-codex-中如何请求同步和归档)
- [6.4.4 归档前检查清单](#644-归档前检查清单)

实现完成不等于正式规格已经更新。Change 内 `specs/` 是本次变更的 delta spec；`openspec/specs/` 才是项目当前已经生效的正式行为来源。完成一个 Change 的收尾顺序是：

```text
代码、测试和人工验收通过
    -> 同步 delta spec 到主规格
        -> 严格校验主规格和 Change
            -> 归档 Change
```

#### 6.4.1 正式规格、delta spec 与归档的分工

三者保存的信息不同：

| 位置或动作 | 保存什么 | 何时使用 |
|---|---|---|
| `openspec/changes/<change-name>/specs/` | 本次 Change 对已有能力的增量要求 | 规划、实现和评审期间 |
| `openspec/specs/<capability>/spec.md` | 当前已经验收且生效的完整行为 | 下一次 Change 的基线和长期验收依据 |
| `openspec/changes/archive/` | 历史的 proposal、design、tasks、delta spec 和验收记录 | 追溯决策、范围和实施证据 |

`openspec-sync-specs` 是 Codex 的工作流 Skill，不是需要直接在终端输入的 OpenSpec CLI 子命令。它会读取 delta spec 与对应主规格，按 `ADDED`、`MODIFIED`、`REMOVED` 和 `RENAMED` 的语义合并，并保留主规格中没有被本次 Change 修改的 Requirement 和 Scenario。

同步只更新正式规格，不会归档 Change，也不会修改业务代码。`openspec-archive-change` 则负责检查完成状态并将完整 Change 工件移入归档目录；归档不是简单移动文件，也不能代替规格同步。

#### 6.4.2 连续迭代同一能力时的同步顺序

同一能力可能因为验收反馈经历多个连续 Change。此时不能只用最后一份 delta spec 覆盖主规格，也不能把多份 delta spec 直接拼接。应按照实际发生顺序同步：

```text
基础能力 Change
    -> 修正或增强 Change
        -> 最终体验优化 Change
            -> 主规格
```

本项目的流式 Chat 是一个实际案例：

1. `llm-chat-streaming` 定义 SSE 流式接口、错误和取消语义，以及前端流式生命周期。
2. `improve-chat-stream-visibility` 补充多个增量到达时必须可观察地渲染的规则。
3. `add-chat-stream-pacing` 将最终展示规则收敛为 Unicode 可读字符组的打字机节奏与积压加速排空。

同步后的 `llm-chat` 主规格必须同时保留第一份的后端 SSE 契约，并采用第三份已验收的前端展示规则。这一做法保留完整能力，而不是只保留最后一次优化。

#### 6.4.3 在 Codex 中如何请求同步和归档

同步单个 Change 时可以这样说：

```text
请使用 openspec-sync-specs，
将 <change-name> 的 delta spec 同步到主规格。
先说明会修改哪些 Requirement，确认后再更新。
```

需要收尾一组连续 Change 时，应同时提供名称和顺序：

```text
请使用 openspec-sync-specs，按以下顺序同步同一能力的连续 Change：
1. <基础-change>
2. <增强-change>
3. <最终优化-change>

完成后严格校验主规格，再使用 openspec-archive-change 依次归档它们。
```

归档单个 Change 时可以这样说：

```text
请使用 openspec-archive-change 归档 <change-name>。
先检查 artifacts、tasks 和 delta spec 同步状态；
若主规格尚未同步，先同步并严格校验后再归档。
```

#### 6.4.4 归档前检查清单

- `proposal`、`specs`、`design` 和 `tasks` 均完整。
- `tasks.md` 没有未完成的复选框任务。
- 对应代码、测试、构建和人工验收已经通过，并且有可追溯证据。
- 所有 delta spec 已同步到主规格；如果跳过同步，必须说明原因和影响。
- 使用 `openspec validate <change-name> --strict` 校验 Change；同步主规格后再执行项目级严格校验。
- 归档路径未与既有历史目录冲突。

## 7. CLI 常用操作

### 7.1 如何阅读命令格式

以这条帮助为例：

```text
openspec new change [options] <name>
```

它不是一条必须原样复制的字符串，而是命令的结构说明：

```text
openspec             程序
└── new               一级命令：创建新条目
    └── change        二级命令：创建 Change
        ├── [options] 可选选项，例如 --description、--goal
        └── <name>    必填的位置参数，例如 llm-chat-streaming
```

- 方括号 `[options]` 表示可以省略的选项，不需要把单词 `options` 输入进去。
- 尖括号 `<name>` 表示必须替换成实际名称，也不需要输入尖括号本身。
- `new change` 是命令层级，不是一个选项；因此创建 Change 要输入 `openspec new change`。
- 当前 CLI 允许把命名选项放在 `<name>` 前面或后面，例如以下两种写法等价：

```powershell
openspec new change `
  --description "将 LLM 单轮对话改为支持流式输出" `
  --goal "让用户在模型生成过程中逐步看到回答内容" `
  llm-chat-streaming

openspec new change llm-chat-streaming `
  --description "将 LLM 单轮对话改为支持流式输出" `
  --goal "让用户在模型生成过程中逐步看到回答内容"
```

再以这条命令为例：

```powershell
openspec instructions --change llm-chat-streaming --json proposal
```

这里 `--change` 和 `--json` 是命名选项，最后的 `proposal` 是 `[artifact]` 位置参数。`proposal` 不是 `instructions` 的子命令；它表示要获取哪个 artifact 的编写指令。具体可用名称以 `openspec status --change <change-name> --json` 输出的 `artifacts[].id` 为准。

### 7.2 CLI 初始化与基础状态查询

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

### 7.3 Change 与 Apply 操作

#### 7.3.1 查看 Apply 任务及完成进度

查看 apply 任务及完成进度：

```powershell
& $cli instructions apply --change <change-name> --json
& $cli list --json
```

其中 `instructions apply` 会列出 `progress.total`、`progress.complete`、`progress.remaining` 和每项任务的 `done` 状态；`list --json` 适合快速查看所有 Change 的 `completedTasks`、`totalTasks` 和 `status`。

#### 7.3.2 其他 Change 和 artifact 操作

查看正式规格：

```powershell
& $cli list --specs --json
& $cli show <spec-name>
```

创建 Change：

```powershell
& $cli new change tender-agent-input `
  --description "招标文件上传与准入校验" `
  --goal "让系统可以接受合法招标文件并返回准入结果"
```

查看某个 artifact 的编写指令：

```powershell
& $cli instructions --change <change-name> --json proposal
& $cli instructions --change <change-name> --json specs
& $cli instructions --change <change-name> --json design
& $cli instructions --change <change-name> --json tasks
```

这里的 `proposal`、`specs`、`design` 和 `tasks` 是 `instructions` 的位置参数，不是 `instructions` 的子命令。可用的 artifact ID 以 `status` 输出中的 `artifacts[].id` 为准。

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

执行归档前，先使用 `openspec-sync-specs` 将该 Change 的 delta spec 合并到主规格。`sync-specs` 是 Codex Skill，不是这里展示的 CLI 子命令；其具体流程见 [6.4 Sync 与 Archive](#64-sync-与-archive让已完成行为成为正式规格)。归档命令负责移动已完成的 Change 工件，不应替代同步和严格校验。

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
| 已完成 Change | 先同步 delta spec 到 `openspec/specs/`，再归档到 `openspec/changes/archive/` |

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

确认范围后先使用 CLI 创建空 Change：

```powershell
openspec new change <change-name> `
  --description "简短描述" `
  --goal "预期目标"
```

然后按依赖关系逐步获取指令和编写 artifact：

```powershell
openspec status --change <change-name> --json
openspec instructions --change <change-name> --json proposal
```

Proposal 审核通过后，再获取 `specs` 和 `design` 的指令。学习过程中不要直接使用 `/opsx:propose`，避免一次性生成全部 artifacts。

### 第四步：审阅 artifacts

重点检查：

- 是否混入 Task Management
- 是否把未来规划写成当前需求
- Scenario 是否包含失败分支
- tasks 是否有明确完成条件
- design 是否符合现有架构

### 第五步：实现和验证

规划材料审核通过后，可以在当前 Codex 会话继续，也可以新开会话。新会话需要明确 Change 名称、要执行的任务和暂停条件；无论使用哪个会话，都不要让实现范围超出当前任务。

例如只实现一个任务：

```text
请使用 openspec-apply-change，实现 llm-chat-streaming。
先只执行任务 1.1，完成代码和测试后暂停。
```

完成代码和测试后查看进度：

```powershell
openspec instructions apply --change llm-chat-streaming --json
openspec list --json
```

确认相关验证通过后，才把对应任务标为 `[x]`。不要因为 Change 的规划材料完整，就把所有任务一次性标记完成。Apply 阶段完成一个任务不等于整个 Change 完成，也不等于可以归档。

全部任务结束后再执行：

```powershell
& $cli validate --all --strict --no-interactive
```

只有代码、测试、构建和人工验收都完成后，才考虑同步主规格并归档。完整的收尾流程见 [6.4 Sync 与 Archive](#64-sync-与-archive让已完成行为成为正式规格)。

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

### 误区八：把归档当成同步正式规格

归档保存的是 Change 的历史工件；主规格是否正确取决于是否已经将 delta spec 合并到 `openspec/specs/`。归档前应先同步并校验，不能只移动 Change 目录。

### 误区九：连续迭代只保留最后一份 delta spec

同一能力的后续 Change 往往只描述增量优化。同步连续 Change 时必须按发生顺序合并，保留早期 Change 定义的基础契约，并采用最后一次已验收的行为规则。

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
- [x] 使用 `openspec-apply-change` 完成 `llm-chat-streaming` 的 21 项任务
- [x] 完成 `improve-chat-stream-visibility` 的 8 项体验改进任务
- [x] 完成 `add-chat-stream-pacing` 的 6 项打字机展示任务
- [x] 完成前端测试、生产构建和浏览器流式验收
- [x] 理解 delta spec、主规格、同步与归档的职责边界

### 进行中

- [ ] 按顺序同步 `llm-chat-streaming`、`improve-chat-stream-visibility` 和 `add-chat-stream-pacing` 到 `llm-chat` 主规格
- [ ] 严格校验主规格，并使用 `openspec-archive-change` 归档上述三个 Change

### 待完成

- [ ] 使用 `openspec-explore` 分析下一个实际功能
- [ ] 为下一个真实功能独立完成一次“创建 Change → 编写 artifacts → apply → sync → archive”流程
- [ ] 按 Change 逐步替代旧阶段进度文档
- [ ] 满足迁移桥接条件后，再单独删除旧阶段文档

## 15. 一句话记忆

```text
探索问题，明确范围；
写出行为，说明设计；
拆成任务，边做边证；
完成归档，规格生效。
```
