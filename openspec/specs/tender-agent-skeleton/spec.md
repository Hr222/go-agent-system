# tender-agent-skeleton Specification

## Purpose
TBD - created by archiving change tender-agent-v1-mcp-skeleton-generation. Update Purpose after archive.
## Requirements

### Requirement: 浏览器 Tender 请求必须经过受控对话调用

浏览器 MUST 通过已授权的 Interaction、显式确认和 Dialogue Agent Invocation 发起 Tender 骨架生成。系统 MUST NOT 保留一个能直接执行 Tender Application 的浏览器同步 HTTP 入口。

#### Scenario: 浏览器使用旧同步生成地址

- **WHEN** 浏览器请求 `POST /api/v1/agents/tender/skeleton`
- **THEN** 系统返回路由不存在响应
- **AND** 系统不读取上传文件、不调用 Tender Application，也不生成文件资源

#### Scenario: 用户从 Tender 页面发起生成

- **WHEN** 用户访问 `/agents/tender` 并选择发起生成
- **THEN** 页面进入 `/chat`
- **AND** 后续文件上传、能力确认、Agent 调用和结果下载使用现有受控对话链路
- **AND** 页面不发送原始文件或 Base64 内容到旧 Tender 同步地址

### Requirement: 系统接受请求级招标文件并执行一次同步分析

系统 MUST 支持提交一个当前请求使用的 DOCX 招标文件和可选的用户关注点，并在同一次调用中完成分析与骨架生成。系统 MUST 在进入文档解析或 LLM 调用前校验文件类型、文件大小和文件内容；请求不得创建持久任务或保存原始招标文件。

#### Scenario: 提交有效招标文件和关注点

- **WHEN** 用户提交一个格式和大小均符合限制、内容非空的 DOCX 文件以及可选的关注点
- **THEN** 系统在本次请求范围内解析文件
- **AND** Tender Agent 调用结构化 LLM 分析招标文件要求
- **AND** 系统返回结构化分析结果和一个或多个投标骨架文件
- **AND** 系统不生成 `task_id`，不写入政策知识库，也不承诺刷新后恢复本次结果

#### Scenario: 无效文件在分析前被拒绝

- **WHEN** 用户提交空文件、非 DOCX 文件或超过配置大小限制的文件
- **THEN** MCP 调用返回稳定的工具错误
- **AND** 系统不调用文档解析器、Structured LLM 或骨架渲染器
- **AND** 系统不创建持久任务或知识库记录

#### Scenario: 关注点为空或仅包含空白字符

- **WHEN** 用户未填写关注点，或提交的关注点仅包含空白字符
- **THEN** 系统将关注点视为空值并继续使用招标文件执行分析
- **AND** 系统不得因为缺少关注点而补充公司事实或行业常识

### Requirement: 系统从招标文件明确要求中生成投标分析和文件分线

系统 MUST 只根据当前招标文件及用户关注点，生成关键要求、投标文件分线、每个输出文件的章节归属、明确出现的函件表格附件、提交规则和源文档依据。系统不得将项目中标后的服务交付成果直接当作投标文件数量或分卷依据。

#### Scenario: 招标文件明确要求单份投标文件

- **WHEN** 招标文件明确列出一份投标文件的组成，即使项目包含多个评估对象或多个中标后交付成果
- **THEN** 系统将输出类型标记为单卷
- **AND** 系统只生成一份对应的投标骨架文件
- **AND** 系统将投标函、资格材料、商务内容、报价内容或其他明确组成项归入该文件
- **AND** 系统不根据项目对象数量生成多份投标文件

#### Scenario: 招标文件明确要求多个投标分册

- **WHEN** 招标文件明确要求技术标、商务标、报价文件或其他分开装订、密封、电子提交的文件
- **THEN** 系统将输出类型标记为多卷
- **AND** 系统为每个明确要求的分册生成独立输出项
- **AND** 每个输出项包含属于该分册的章节、表格、函件和提交要求
- **AND** 系统不把多个分册合并成一份未被招标文件要求的合订本

#### Scenario: 招标文件无法确定文件分线

- **WHEN** 招标文件中的投标文件组成或分册关系存在无法依据原文消除的歧义
- **THEN** 系统在分析结果中标记待确认项和对应源文档依据
- **AND** 系统不得把不确定的分线静默当作确定结论
- **AND** 系统不得凭行业惯例补充分册或章节

### Requirement: 系统生成可继续填写的投标骨架文件

系统 MUST 根据已校验的投标分析结果生成一个或多个可打开、可继续填写的 DOCX 骨架文件。骨架 MUST 保留招标文件明确给出的标题、章节顺序、函件、表格、附件模板和格式占位；源文件只有要求或标题而没有模板正文时，系统 MUST 保留标题并提供明确的待填写位置，不得编造公司内容。

#### Scenario: 源文件包含函件或表格模板

- **WHEN** 招标文件在投标格式区域中提供函件正文、表格或附件模板
- **THEN** 对应骨架文件包含该模板的可填写版本
- **AND** 模板所属分册和顺序与分析结果一致
- **AND** 生成结果保留必要的原始字段和签章、日期等占位

#### Scenario: 源文件只列出章节或材料名称

- **WHEN** 招标文件明确列出章节或材料名称但未提供对应正文模板
- **THEN** 骨架文件保留该章节或材料名称
- **AND** 系统在对应位置提供待填写占位
- **AND** 系统不生成公司名称、资质、业绩、人员、价格或服务方案内容

#### Scenario: 骨架生成成功

- **WHEN** 投标分析通过 Schema 校验且文档渲染器成功完成
- **THEN** 每个计划输出项均返回文件名、媒体类型和可获取的 DOCX 文件内容
- **AND** 生成的每个文件能够被 DOCX 阅读器打开
- **AND** 返回结果中的输出文件数量、名称和分线与分析结果一致

### Requirement: Tender Agent 提供标准 MCP 工具调用能力

系统 MUST 通过符合 MCP 协议的 Server 暴露已经实现的 Tender Agent function。MCP Server MUST 支持标准工具发现和工具调用，并将协议输入转换为同一个 Tender Application Command；MCP Adapter 不得自行执行文档解析、LLM 调用、文件渲染或知识库访问。

#### Scenario: MCP 客户端发现 V1 工具

- **WHEN** MCP 客户端请求工具列表
- **THEN** 系统返回 `tender.generate_bid_skeleton`、`tender.extract_bid_format_section` 和 `tender.verify_extraction_boundary` 及其结构化输入 Schema
- **AND** 输入 Schema 描述文件名称、文件内容或标准资源引用以及可选用户关注点
- **AND** 工具列表不宣称 `tender.fill_bid_content` 已经可用

#### Scenario: MCP 客户端调用格式章节提取工具

- **WHEN** MCP 客户端使用合法文件内容、起始证据块和结束证据块调用 `tender.extract_bid_format_section`
- **THEN** MCP Server 将请求交给 Tender Application 按确定性 XML 范围提取格式章节
- **AND** 工具结果使用 MCP 标准资源内容返回生成的 DOCX 文件
- **AND** MCP Adapter 不自行读取 DOCX、复制 XML 或访问本地路径

#### Scenario: MCP 客户端调用边界复核工具

- **WHEN** MCP 客户端使用合法文件内容和候选起止证据块调用 `tender.verify_extraction_boundary`
- **THEN** MCP Server 将请求交给 Tender Application 返回候选边界附近的源文档上下文和结构位置
- **AND** 返回结果供 Agent 决定是否调整边界
- **AND** MCP Adapter 不自行执行 LLM 决策

#### Scenario: MCP 客户端调用骨架生成工具

- **WHEN** MCP 客户端使用合法输入调用 `tender.generate_bid_skeleton`
- **THEN** MCP Server 将请求交给 Tender Application 完成一次同步分析
- **AND** 工具结果包含结构化分析、关键要求、文件分线和源文档依据
- **AND** 工具结果使用 MCP 标准内容或资源表达返回生成的 DOCX 文件
- **AND** 三个 MCP 工具使用同一套 Tender Application 业务规则和输出语义

#### Scenario: MCP 客户端提交非法工具输入

- **WHEN** MCP 客户端提交缺少文件、格式不合法或超过大小限制的输入
- **THEN** MCP Server 返回稳定且可理解的工具错误
- **AND** 系统不调用 Tender Application 的 LLM、渲染或知识库能力
- **AND** 错误结果不泄露本地路径、API Key 或未审查的 Provider 异常原文

### Requirement: 系统保证来源追踪、错误隔离和请求资源清理

系统 MUST 为分析中的关键要求、文件分线、章节和风险或待确认项保留当前招标文件中的可用位置依据。系统 MUST 区分输入错误、文档解析失败、LLM 配置缺失、上游失败、结构化结果无效和渲染失败，并在所有请求分支清理临时文件。

#### Scenario: 分析结果包含源文档依据

- **WHEN** 系统返回关键要求、章节分线或待确认项
- **THEN** 每项结果包含可用的段落、章节、页码或其他源文档位置标识
- **AND** 来源只指向本次提交的招标文件
- **AND** 系统不要求或返回公司知识库引用

#### Scenario: Structured LLM 返回不符合契约的结果

- **WHEN** 上游返回无法通过 Tender Schema 校验的结构化结果
- **THEN** MCP 调用返回稳定的结构化结果错误
- **AND** 系统不生成未经校验的骨架文件
- **AND** 请求级临时文件仍然被清理

#### Scenario: 请求在成功或异常分支结束

- **WHEN** Tender 请求成功、解析失败、模型失败、渲染失败或客户端中断
- **THEN** 系统清理本次请求创建的临时文件和临时资源
- **AND** 系统不将招标文件写入政策知识库或持久任务
- **AND** 日志只记录请求标识、能力名称、Prompt 版本、阶段和耗时，不记录原始招标文本或生成文件内容

