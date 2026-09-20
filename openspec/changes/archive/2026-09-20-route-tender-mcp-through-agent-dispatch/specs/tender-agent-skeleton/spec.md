## MODIFIED Requirements

### Requirement: Tender Agent 提供标准 MCP 工具调用能力

系统 MUST 通过符合 MCP 协议的 Server 暴露已经实现的 Tender Agent function。MCP Server
MUST 支持标准工具发现和工具调用，并将协议输入转换为同一个受控的
`StructuredAgentCall`，再交给 `AgentCallDispatcher`；MCP Adapter 不得直接调用
`TenderApplication`，也不得自行执行文档解析、LLM 调用、文件渲染或知识库访问。

#### Scenario: MCP 客户端发现 V1 工具

- **WHEN** MCP 客户端请求工具列表
- **THEN** 系统返回 `tender.generate_bid_skeleton`、`tender.extract_bid_format_section` 和 `tender.verify_extraction_boundary` 及其结构化输入 Schema
- **AND** 输入 Schema 描述文件名称、文件内容或标准资源引用以及可选用户关注点
- **AND** 工具列表不宣称 `tender.fill_bid_content` 已经可用

#### Scenario: MCP 客户端调用格式章节提取工具

- **WHEN** MCP 客户端使用合法文件内容、起始证据块和结束证据块调用 `tender.extract_bid_format_section`
- **THEN** MCP Server 将请求转换为固定能力的结构化调用并交给 `AgentCallDispatcher`
- **AND** Dispatcher 按当前目录和主体权限调用 Tender Application 的确定性 XML 范围提取能力
- **AND** 工具结果使用 MCP 标准资源内容返回生成的 DOCX 文件
- **AND** MCP Adapter 不自行读取 DOCX、复制 XML 或访问本地路径

#### Scenario: MCP 客户端调用边界复核工具

- **WHEN** MCP 客户端使用合法文件内容和候选起止证据块调用 `tender.verify_extraction_boundary`
- **THEN** MCP Server 将请求转换为固定能力的结构化调用并交给 `AgentCallDispatcher`
- **AND** Dispatcher 按当前目录和主体权限调用 Tender Application 返回候选边界附近的源文档上下文和结构位置
- **AND** 返回结果供 Agent 决定是否调整边界
- **AND** MCP Adapter 不自行执行 DOCX 解析或 LLM 决策

#### Scenario: MCP 客户端调用骨架生成工具

- **WHEN** MCP 客户端使用合法输入调用 `tender.generate_bid_skeleton`
- **THEN** MCP Server 将请求转换为固定能力的结构化调用并交给 `AgentCallDispatcher`
- **AND** Dispatcher 完成一次同步 Tender 分析
- **AND** 工具结果包含结构化分析、关键要求、文件分线和源文档依据
- **AND** 工具结果使用 MCP 标准内容或资源表达返回生成的 DOCX 文件
- **AND** 三个 MCP 工具使用同一套 Tender Application 业务规则和输出语义

#### Scenario: MCP 客户端提交非法工具输入

- **WHEN** MCP 客户端提交缺少文件、格式不合法或超过大小限制的输入
- **THEN** MCP Server 返回稳定且可理解的工具错误
- **AND** 系统不调用 Agent Runtime、Tender Application 的 LLM、渲染或知识库能力
- **AND** 错误结果不泄露本地路径、API Key 或未审查的 Provider 异常原文
