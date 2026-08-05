## Why

当前项目已经具备通用 Structured LLM 调用能力，但还没有一个真正可调用的 Tender Agent。旧的招标文档 skill 中积累了大量 demo 和文档生成经验，却不能作为当前系统的业务基板；招标文件的单卷、多卷、章节归属和服务交付成果区分，需要由 LLM 理解并由 Agent 组织完成。

Phase 3 需要先交付一个可被后续 SubAgent 编排调用的稳定业务能力：Tender Agent 读取当前招标 DOCX，提取招标方明确要求，生成一份或多份可填写的投标骨架文件。骨架生成是该 Agent 的第一个 function；后续公司资料填充将作为同一 Agent 的 V2 function 接入。

## What Changes

- 新增 Tender Agent V1 业务能力，支持从当前请求中的招标 DOCX 分析投标文件要求。
- 生成关键要求、文件分线点、章节、表格、函件、附件和可追溯的源文档依据。
- 根据招标文件明确要求判断单卷或多卷，并生成对应数量和名称的投标骨架 DOCX。
- 对源文件只给出标题或占位的内容保留待填写位置，不凭行业常识补充章节，不生成公司事实。
- 通过标准 MCP Server 暴露已经实现的 Tender Agent function，支持标准的工具发现和工具调用。
- 将 Phase 3 文档中的边界调整为“实现 MCP 能力适配，不实现 Agent Runtime、SubAgent 编排或多 Agent 运行时”。
- 让三个 MCP 工具共用同一个 Tender Application，避免协议层重复实现业务逻辑。
- 预留同一 Tender Agent 的 V2 `fill_bid_content` 能力契约，但本 Change 不接入公司资料库、不执行内容填充。
- 使用 `D:\workspace\bid-tech-generator\demo` 中排除 `_skill_test` 的代表样本进行本轮 V1 回归，抽取 1 个单卷和 1 个多卷；历史 20 个样本结构探针作为离线回归资产保留。
- 不创建任务、会话历史、持久化招标文件或 SubAgent 编排流程。

## Capabilities

### New Capabilities

- `tender-agent-skeleton`: 定义 Tender Agent 的投标要求分析、单卷/多卷分线、投标骨架文件生成，以及通过 MCP 调用该能力的可观察行为。

### Modified Capabilities

无。当前没有已生效的 Tender Agent 主规格；现有 `llm-chat` 能力只提供通用 LLM 单轮调用，不在本 Change 中修改。

## Impact

- 后端新增 `agent/tender` 的 Application、Domain/Ports 和 DOCX 解析、骨架渲染适配器，并在 Composition Root 中组装。
- `interfaces/agent` 新增 MCP 协议适配边界；MCP Adapter 只调用 Tender Application，不直接访问模型 SDK、解析器或文件系统。
- 本 Change 不包含 HTTP 页面和前端交互；现有页面由后续独立 Change 承接。
- 需要接入 DOCX 文件处理能力和现有 Structured LLM Port；外部模型在自动化测试中使用稳定替身。
- 请求文件只在请求生命周期内解析和清理，不写入政策知识库、不进入长期存储。
- 不涉及数据库结构、持久化迁移、Conversation、Task Management 或现有 `llm-chat` 接口兼容性。
- MCP 暴露新的外部能力入口，需要对输入大小、文件类型、临时文件路径和错误信息进行校验，避免泄露密钥、临时路径或未审查的 Provider 异常。
