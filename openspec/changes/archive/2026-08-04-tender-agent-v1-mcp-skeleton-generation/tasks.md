## 1. Tender Agent 契约与能力边界

- [x] 1.1 定义 Tender Application 的 Command、Result、错误语义和结构化投标分析模型，覆盖单卷/多卷、关键要求、分线、源文档依据、待确认项和生成文件元数据；完成条件：模型可独立完成校验，且字段与 `tender-agent-skeleton` 规格一致。
- [x] 1.2 定义 Tender Agent 的能力注册边界和 V1 `generate_bid_skeleton`、`extract_bid_format_section`、`verify_extraction_boundary` 能力，预留 V2 `fill_bid_content` 的输入输出 Port 但不组装公司资料 Provider；完成条件：V1 三个能力可被 MCP 发现和调用，V2 不出现在可用 MCP 工具列表中。
- [x] 1.3 补充 V1 Prompt 模板和版本标识，明确只使用当前招标文件与用户关注点、不得补充公司事实、必须输出源文档依据；完成条件：Fake LLM 测试能断言 Prompt 版本和关键约束已传入。

## 2. 文档解析与骨架渲染

- [x] 2.1 实现请求级 DOCX Reader Port 和适配器，提取段落、标题、表格、附件/模板区块及可用位置证据，并确保输入文件只在临时目录中处理；完成条件：覆盖有效 DOCX、空文件、非 DOCX、超限和解析失败测试，所有分支清理临时资源。
- [x] 2.2 实现 Skeleton Renderer Port 和 DOCX 适配器，按已校验的分析结果生成单卷或多卷文件，保留源模板、表格、占位和章节顺序；完成条件：生成的每个 DOCX 可被文档库重新打开，且不写入公司事实或未授权章节。
- [x] 2.3 为解析器和渲染器补充合成单卷、多卷、模板缺失、表格和附件样本测试；完成条件：测试能验证文件分线和模板复制，不依赖真实 LLM 或外部服务。

## 3. Tender Application 主链路

- [x] 3.1 实现 Tender Application 的同步用例，按“输入校验 -> 文档解析 -> Structured LLM -> Schema 校验 -> 骨架渲染 -> 结果组装”顺序编排；完成条件：Application 只依赖 Ports，不直接依赖 FastAPI、MCP SDK、LangChain 或 DOCX 库。
- [x] 3.2 实现单卷、多卷、服务交付成果区分、来源证据校验和歧义待确认处理；完成条件：单卷和多卷 Fake LLM 场景输出数量、名称、章节归属与分析结果一致，歧义不会被静默补全。
- [x] 3.3 实现配置缺失、上游失败、结构化结果无效、渲染失败和客户端中断的稳定错误转换；完成条件：每类错误都有可断言的业务错误，且成功、失败和中断分支均释放临时资源。
- [x] 3.4 在 Composition Root 中组装 Tender Application、Structured LLM、Document Reader、Skeleton Renderer 和 V2 预留 Port；完成条件：测试容器可注入 Fake，真实容器不要求数据库会话即可构造请求级 Tender 能力。

## 4. MCP 协议适配

- [x] 4.1 引入兼容项目 Python 版本的官方 MCP SDK，并建立独立的 MCP Server/Adapter；完成条件：MCP 适配层不直接调用 LLM、文档库、Repository 或文件系统，并通过现有 Composition Root 获取 Application。
- [x] 4.2 实现标准 `tools/list` 和 `tools/call`，注册 `tender.generate_bid_skeleton`、`tender.extract_bid_format_section` 和 `tender.verify_extraction_boundary` 的 JSON Schema 输入，并将文件内容或标准资源转换为对应 Application Command；完成条件：工具列表只暴露已实现的 V1 能力，非法输入返回稳定工具错误。
- [x] 4.3 将结构化分析和生成 DOCX 按 MCP 标准内容/资源结果返回，并建立 Streamable HTTP 挂载入口；完成条件：MCP 客户端可以发现工具、完成一次同步调用并读取至少一个生成文件。
- [x] 4.4 编写 MCP 协议 smoke、错误和资源返回测试；完成条件：Fake Application 下测试覆盖成功、输入失败和 Application 失败，且不泄露本地路径、密钥或 Provider 原文。

## 5. V1 样本验收与架构验证

- [x] 6.1 从 `D:\workspace\bid-tech-generator\demo` 中排除 `_skill_test`，选取 1 个单卷代表样本 S01 和 1 个多卷代表样本 M01，记录预期输出数量、文件分线和关键结构；完成条件：测试清单以源招标文件为依据，不把目录名称直接当作答案。
- [x] 6.2 使用真实或脱敏样本完成 2 个 V1 代表性验收（1 个单卷、1 个多卷），检查输出数量和名称、章节与表格完整性、服务交付成果区分、源文档追溯、无公司事实编造和 DOCX 可打开；完成条件：两个样本均有成功、待确认或失败的可解释记录，生成 DOCX 保存到临时目录并交由真人打开检查；用户已完成当前产物人工核对并确认通过。
- [x] 6.3 补充或更新 Agent Protocol、Composition Root、模块依赖和临时文件清理的架构边界测试；完成条件：测试证明 MCP Adapter 只依赖 Application，Tender Domain/Application 不依赖 FastAPI、MCP SDK、DOCX 库或具体 Provider。
- [x] 6.4 同步更新 `docs/第三阶段工作计划.md`、`docs/第三阶段- 前后端联合工作进度.md`、`docs/go agent system - 系统看板.md` 和必要的阶段过渡上下文，明确 V1 包含 MCP 能力适配，但不包含 Agent Runtime、SubAgent 编排、Task Management、Conversation 或 V2 资料填充；完成条件：相关文档不再把本 Change 要求的 MCP 适配错误列为本阶段明确不做项。

## 6. 完整验证与交付记录

- [x] 7.1 执行后端 pytest、`ruff check app tests` 和 `python -m compileall -q app tests`；完成条件：相关测试和静态检查通过，失败项有明确记录。
- [x] 7.2 完成 MCP 工具发现、工具调用和资源返回联调，记录至少一个单卷和一个多卷结果及失败分支证据；完成条件：工具调用和 DOCX 资源返回均可追溯，且生成 DOCX 经真人打开并明确确认通过。
- [x] 7.3 更新 tasks 中的验证证据、Change 状态和必要的验收说明；完成条件：所有本 change 范围内任务均有对应代码、测试、构建或人工证据后，具备同步规格和归档条件。

## 验证证据（2026-07-30）

- `python tools/tender_v1_sample_probe.py` 已可直接执行，结果为 20/20 个样本结构通过：单卷 10 个、每个输出 1 个 DOCX；多卷 10 个、每个输出 2 个 DOCX；每个生成文件均可重新打开。
- 历史 20 个样本的结构探针语义仍标记为 `structural_pass_semantic_unverified`，不纳入本轮真实调用；本轮 6.2 只验证 S01 单卷和 M01 多卷两个代表样本。
- 浏览器人工联调已覆盖单卷和多卷上传、提交中状态、真实 Provider 失败和显式重试。两次真实调用均约 182 秒后返回 `REQUEST_FAILED`，尚未产生可下载的真实成功 DOCX，因此 7.2 保持未完成。
- MCP Fake Application、协议 smoke、资源返回和错误映射测试已通过；HTTP API 和前端页面不属于本 change 的完成条件，后续由独立 change 承接。
- GLM 诊断已确认网络、API Key、普通 Chat 和 `json_object` 基础能力可用；Tender 失败发生在约 40,498 字符的大输入结构化请求上，原始异常为 `APITimeoutError -> httpx.ReadTimeout -> httpcore.ReadTimeout`。结构化适配器已改为 raw OpenAI-compatible JSON Object 调用并修复 `human -> user` 角色映射，但真实 Tender 成功结果仍未取得。

## 验证证据（2026-08-04）

- MCP 工具已注册并通过 Fake Application 的 `tools/list`、`tools/call`、错误和资源返回测试；新增的格式章节提取与边界上下文工具不调用 LLM 决策。
- `tmp/tender_extractor_single` 和 `tmp/tender_extractor_multi` 的单卷/多卷核心逻辑已接入正式 Tender Application/MCP；用户已人工核对当前输出并确认通过。
- 本 change 不包含 HTTP 页面和前端联调；现有 HTTP/前端代码保留，后续另立 change 管理。
