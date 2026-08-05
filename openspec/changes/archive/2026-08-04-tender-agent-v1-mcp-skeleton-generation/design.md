## Context

当前仓库已经有通用 Structured LLM Port、GLM 适配器和 Composition Root，但 `app/modules/agent/tender` 还没有 Tender Application、业务契约或真实文件产出能力。Phase 3 的目标是完成一次真实、同步的 Tender Agent 调用；本 Change 将这次业务能力定义为 Tender Agent 的第一个可调用 function，并通过 MCP 作为后续 SubAgent 编排的外部接入边界。

旧的招标文档 skill 及其 demo 只作为样本和文档生成经验参考，不作为新系统的规则基板。demo 不进入运行时，也不作为 Prompt 中的固定模板。V1 只处理当前请求中的招标 DOCX，不读取公司资料库，不写入政策知识库，不创建持久任务或会话。

## Goals / Non-Goals

**Goals:**

- 建立单一 Tender Agent 的稳定业务能力边界。
- 通过 LLM 理解招标文件明确给出的投标要求，并输出关键要求、文件分线点和源文档依据。
- 根据源文件要求生成一份或多份可继续填写的投标骨架 DOCX。
- 通过标准 MCP 工具调用暴露三个 V1 能力，并复用同一个 Application 用例。
- 预留同一 Agent 后续 `fill_bid_content` function 的能力端口和结果边界。
- 使用 2 个脱敏或可用 demo 代表样本进行本轮 V1 回归：单卷 1 个、多卷 1 个，排除 `_skill_test`；历史 20 个样本结构探针仅作为离线回归资产。

**Non-Goals:**

- 不实现 Agent Runtime、LangGraph、SubAgent 编排、多 Agent 调度或任务恢复。
- 不实现公司资料库检索、资料不足判断、公司内容填充、建议或知识库引用；这些属于 V2。
- 不生成完整投标正文，不替用户填写公司事实，不替代人工确认和正式投标提交。
- 不把招标文件写入政策知识库，不建立招标文件长期存储、任务 ID、会话历史或上下文记忆。
- 不迁移旧 skill 的脚本、规则、Prompt 或 demo 到生产运行时。
- 不在 V1 的 MCP `tools/list` 中暴露尚未实现的资料填充工具。

## Decisions

### 1. 一个 Agent，多个可扩展能力

Tender Agent 作为业务能力承载者，不把 V1 和 V2 拆成两个 Agent。V1 注册 `tender.generate_bid_skeleton`、`tender.extract_bid_format_section` 和 `tender.verify_extraction_boundary` 三个能力：前者完成完整骨架用例，后两者分别承载格式章节的确定性提取和边界复核所需的请求级操作。V2 预留 `tender.fill_bid_content` 的能力契约，后续使用 V1 的骨架和公司资料输入完成填充。

Agent 内部通过能力注册边界区分不同 function，但本 Change 不引入通用 Agent Runtime。这样后续 SubAgent 编排可以通过 MCP 调用稳定的能力名称，而不需要依赖 Tender Agent 的 Python 内部结构。

替代方案是只实现一个临时 RPC Endpoint，或现在就引入 LangGraph 编排。前者会导致后续 Agent 接入重新设计，后者超出 Phase 3 的单 Agent 交付范围，因此不采用。

### 2. Application 统一编排，协议层只做适配

Tender Application 接收业务 Command，完成请求级文件解析、Prompt 输入准备、Structured LLM 调用、结果校验、骨架渲染、格式范围提取和错误转换。MCP Adapter 只负责协议解析、依赖注入、Assembler 和错误映射，不直接访问 LLM SDK、DOCX 库、临时文件或 Repository。

依赖方向保持为：

```text
MCP Adapter
  -> Tender Application
      -> Document Reader Port
      -> Structured LLM Port
      -> Skeleton Renderer Port
  <- Infrastructure Adapters
```

具体实现由 Composition Root 组装。Tender Domain/Ports 不依赖 FastAPI、MCP SDK、LangChain、DOCX 库或具体模型供应商。

### 3. LLM 负责理解，确定性工具负责文件处理

请求级文档解析器把段落、表格、标题层级和可用位置整理为带证据标识的输入。Prompt 要求 LLM 只根据当前招标文件和用户关注点输出结构化的投标计划，至少包含：

- 单卷或多卷判断；
- 每个输出文件的名称、用途和章节归属；
- 明确要求的函件、表格、附件和提交规则；
- 可填写占位与源文档证据位置；
- 无法确定时的待确认项。

Structured LLM 结果必须经过 Schema 校验。骨架渲染器根据通过校验的证据位置复制源文档中的显式内容和模板表格；只出现标题或要求但没有正文时，保留标题和待填写占位。系统不得根据行业常识补章节，不得把项目中标后的报告等服务交付成果误判成投标分卷，也不得生成公司事实。

替代方案是继续使用正则和固定关键词直接决定单卷、多卷和章节边界。旧 demo 已证明该方式容易受到文档排版、目录和措辞变化影响，因此只保留确定性解析和渲染工具，不让它承担招标语义判断。

### 4. MCP 使用标准工具协议，不自定义 Agent RPC

通过官方 Python MCP SDK 建立 MCP Server，V1 采用与现有后端共存的 Streamable HTTP 传输。MCP Adapter 实现标准的工具发现和工具调用语义：

- `tools/list` 只返回已实现的 `tender.generate_bid_skeleton`、`tender.extract_bid_format_section` 和 `tender.verify_extraction_boundary`；
- `tools/call` 使用 JSON Schema 描述文件内容、文件名和用户关注点；
- `tender.extract_bid_format_section` 接收源文件内容和已确定的起止证据块，执行确定性的 XML 范围提取并返回 DOCX 资源；
- `tender.verify_extraction_boundary` 接收源文件内容和候选起止证据块，返回边界上下文及结构位置供 Agent 复核，不在 MCP Adapter 中执行 LLM 决策；
- 调用结果通过标准结构化内容返回分析结果，并用标准资源内容返回生成的 DOCX；
- 参数错误、文件解析失败、模型失败和骨架生成失败使用稳定的工具错误结果，不泄露 Provider 原文、密钥或本地临时路径。

MCP 工具输入不能依赖服务端本地路径。V1 使用请求级文件内容完成同步调用，不引入持久资源存储。

替代方案是在 MCP Adapter 中重复实现一套 Tender 业务流程。这样会导致协议层和业务层结果分叉，因此不采用。

### 5. V2 插口只定义边界，不提前实现资料填充

V2 使用独立的资料输入端口和填充结果契约，输入至少引用 V1 生成的骨架计划或文件，输出按章节返回填充结果、缺失资料、建议和引用。V1 的 Composition Root 不组装公司资料 Provider，V1 的 Prompt 也不要求模型生成公司内容。

V2 function 的名称和能力端口在设计与任务中固定，但不在 V1 MCP 工具列表中注册，不返回虚假的“已实现”状态。未来接入资料库时，新增 Change 只实现该 function，并保持 V1 骨架生成契约不变。

### 6. 文件、错误和生命周期

输入文件在请求生命周期内完成类型、大小和空内容校验，写入受控临时目录，成功、失败和取消分支均在 `finally` 中清理。系统不保存原始招标文件，不把它送入政策知识库入库链路。

MCP 使用稳定的业务错误语义：输入不合法、文件解析失败、LLM 配置缺失、上游模型失败、结构化结果无效和文件渲染失败均可区分，并转换为标准工具错误结果。

日志只记录请求标识、能力名称、Prompt 版本、阶段和耗时，不记录原始招标文本、用户关注点、生成文件内容或敏感配置。

### 7. 验收样本作为外部回归资产

本轮 V1 回归使用 `D:\workspace\bid-tech-generator\demo` 下排除 `_skill_test` 的 2 个代表样本：单卷选 S01，多卷选 M01；目录名称不作为最终正确答案，最终以源招标文件的明确要求为准。历史 20 个样本结构探针不删除，但不再作为本轮真实模型调用范围。

验收关注业务结果：输出数量和名称、分卷归属、章节与表格完整性、服务交付成果与投标文件的区分、源文档可追溯性、无公司事实编造以及 DOCX 可打开。机器只能完成结构检查，最终 DOCX 必须保存到临时目录并由真人打开检查、明确确认通过；没有人工确认不能完成 V1 验收任务。样本路径作为本地验收前提，不作为生产运行时依赖，也不要求把真实样本提交到仓库。

## Risks / Trade-offs

- [风险] 招标文件排版和表达变化较大，LLM 可能遗漏或错误归类要求。→ 使用结构化 Schema、源证据、结果校验和单卷/多卷分层样本验收；无法确认时明确标记待确认，不静默补全。
- [风险] DOCX 包含复杂样式、表格或附件时，生成结果可能与源文件视觉效果有差异。→ 把文档复制和渲染隔离在独立 Adapter，保留源模板块，并对生成文件执行打开和人工检查。
- [风险] MCP 文件内容通过协议传输可能增加请求体和响应体大小。→ V1 设置明确的文件大小限制，使用请求级资源结果；需要持久资源或大文件传输时另建 Change。
- [风险] MCP SDK、模型供应商和 DOCX 处理库都是外部依赖。→ 业务层只依赖 Ports，自动化测试使用 Fake，具体适配器集中在 Infrastructure 和 Composition Root。
- [风险] Phase 3 文档当前将 MCP 列为不做项。→ 本 Change 的任务中同步修改阶段边界，明确“不做 MCP 编排”与“实现 MCP 能力适配”的区别。

## Migration Plan

无数据库迁移、历史数据迁移或持久化回滚步骤。实现阶段先完成 Application、Ports、Fake 和离线测试，再接入 DOCX、LLM 和 MCP 适配器，最后对 1 个单卷和 1 个多卷 demo 进行真实或脱敏联调。

如果 MCP 适配器出现问题，可以暂时关闭 MCP 路由而不影响已有 Chat、Knowledge 和 Ingestion 能力；前端和 HTTP 展示由后续 Change 单独验收。

## Open Questions

- MCP Streamable HTTP 的具体挂载路径、鉴权方式和部署入口需要结合现有服务部署配置在实现任务中确定；V1 不新增独立服务进程。
