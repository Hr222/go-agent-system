## 1. 原始响应与归一化契约

- [x] 1.1 定义 Provider 原始结构化响应模型，保留 Provider、模型、业务内容、可选思考内容、响应格式分类和脱敏元数据；完成条件：契约不包含完整招标正文、API Key 或完整思考原文的日志要求，并可被测试替身使用。
- [x] 1.2 定义 Provider 输出归一化器接口和归一化装饰器，保持现有 `StructuredLlmPort`、`StructuredLlmResult` 和 Tender Application 调用方式不变；完成条件：装饰器只能在原始响应归一化和目标 Schema 校验完成后返回成功结果。
- [x] 1.3 在 Composition Root 中增加 Provider/模型到归一化器的组装或注册边界；完成条件：Tender Application 不出现 Provider 名称分支，未注册格式可以稳定失败。

## 2. 公共归一化流程

- [x] 2.1 实现响应内容提取、明确 JSON 代码块去除、已声明思考字段隔离和 JSON object 解析；完成条件：公共流程不把思考内容混入业务 JSON，不对普通自然语言做无规则猜测。
- [x] 2.2 实现有限的已知包装解包和目标 Schema 严格校验；完成条件：只接受与目标 Schema 或 Provider 映射匹配的包装键，未知包装、多候选结果和字段类型错误均返回稳定失败。
- [x] 2.3 实现归一化错误映射和脱敏诊断日志；完成条件：日志包含 Provider、模型、Schema、响应格式分类、阶段、耗时和异常类型，不包含招标正文、用户关注点、思考原文、API Key 或完整响应。

## 3. OpenAI-compatible Provider 归一化适配

- [x] 3.1 将现有 OpenAI-compatible 结构化调用拆分为原始 Provider 响应获取和归一化装配，保留现有 JSON Object 请求和 `human -> user` 角色映射；完成条件：GLM 和 DeepSeek 原始响应均可交给归一化层，现有普通 Chat 适配器行为不受影响。
- [x] 3.2 实现通用 Schema 感知归一化，支持直接 JSON、`tender_analysis`、`tender_chunk_analysis` 包装对象；完成条件：解包后的 `TenderAnalysis` 和 `TenderChunkAnalysis` 通过本地 Pydantic 校验并保留模型与 Prompt 版本。
- [x] 3.3 对所有 Provider 的字段类型不匹配和不确定包装保持失败闭合；完成条件：不通过字符串化对象、丢字段或再次调用 LLM 修复响应来制造成功结果。

## 4. 测试与架构边界

- [x] 4.1 补充归一化器单元测试，覆盖直接 JSON、已知包装、Markdown 代码块、独立思考字段、无效 JSON、未知包装、多个候选和字段类型错误；完成条件：每个分支都有可断言的结构化结果或稳定异常。
- [x] 4.2 补充 GLM/DeepSeek Adapter 和 Composition Root 回归测试；完成条件：Fake Raw Adapter 能验证通用归一化装饰层被调用，`StructuredLlmPort` 契约、现有 Chat 行为和模型元数据保持兼容。
- [x] 4.3 补充架构边界检查；完成条件：Tender Application、Tender Domain、HTTP 和 MCP 不依赖具体 Provider Normalizer、SDK 或原始响应结构。

## 5. 真实验收与交付记录

- [x] 5.1 使用真实 Demo Tender 文件验证“原始响应 -> GLM 归一化 -> Tender Schema”链路；完成条件：真实招标文件的模型结果能够进入 Application 后续流程，失败时记录格式分类和诊断信息。
- [x] 5.2 使用真实单卷和多卷 Demo 验证归一化后继续执行分块、全局归并和 DOCX 渲染；完成条件：至少一个单卷和一个多卷请求取得真实分析结果与可打开的 DOCX，语义分线和章节仍需人工确认。
- [x] 5.3 通过 `tools/tender_mcp_acceptance_probe.py` 使用真实单卷和多卷样本调用 Streamable HTTP MCP 工具；完成条件：输出脱敏 `result.json` 和生成的 DOCX，记录 MCP 入口、分块/归并结果、文件数量和可打开性，DOCX 业务内容由人工验收。
- [x] 5.4 使用真实单卷和多卷样本完成前端验收；完成条件：浏览器上传、加载态防重复提交、分析结果展示、所有 DOCX 下载、失败重试和无 `task_id` 行为均由人工确认，前端不展示内部 LLM 批次。

## 验证证据（2026-07-30）

- 模型配置已切换为 `glm-5`，`.env` 和 `.env.example` 已同步；网络、DNS、HTTPS `/models` 正常。
- 真实 GLM5 Tender 分块 smoke：输入 154 字符，约 9.9 秒返回，包装归一化和 `TenderChunkAnalysis` 校验通过。
- 合成极小 DOCX smoke：明确传入单卷关注点后，约 46.7 秒完成结构化结果和占位文件生成；该输入只有三句话，不属于真实招标文件，不能作为 Tender V1 业务验收。其输出只用于验证归一化、Application 和 Renderer 的连通性，不能作为真实骨架交付物。
- 真实 Demo 单卷：39,554 字节样本完成前 3 个分块，第四个约 9KB 分块两次各 60 秒超时；未进入归并和 DOCX 生成。
- 真实 Demo 多卷：261,593 字节、2 分块样本在第一个大分块两次各 60 秒超时；未进入归并和 DOCX 生成。
- 另一份最小文本量 Demo 单卷已进入最终业务校验，但模型输出数量不符合单卷规则，系统稳定拒绝，未生成不可信文件。
- 自动化验证：新增归一化/GLM/架构相关测试 37 passed；全后端 `pytest -q` 为 186 passed；`ruff check app tests`、`compileall` 和 OpenSpec strict validation 均通过。`ruff check app tests tools` 仍受 `tools/ocr/` 中 3 个与本 Change 无关的既有 E501 阻塞。
- DOCX 结构读取通过；LibreOffice headless 转 PDF 在原文件名和 ASCII QA 副本上均退出码 1，视觉 PNG QA 受本机渲染环境阻塞，不能据此宣称视觉验收完成。
- 结论：GLM5 输出归一化和合成 Renderer smoke 已验证；真实 Demo 的完整单卷/多卷业务验收仍未完成，现有两个 Tender Change 继续保持不可归档。
- 追加验证：最小真实单卷样本（39,554 字节）在 180 秒 Provider 超时、6,000 字符分块预算下完成分块调用；所有分块结果均经过 GLM-5 归一化并通过 `TenderChunkAnalysis` 校验，随后进入 Application 归并阶段。归并调用在 180 秒后以 `APITimeoutError` 失败，归一化日志记录 `schema=TenderAnalysis`、`format=raw_call_failed` 和异常类型，未记录原文或密钥。
- 追加验证：按解析文本量选择的最小真实单卷样本（DOCX 42,165 字节、解析文本约 1,380 字符）在 GLM-5 下完成分块、归并和渲染，耗时约 207.62 秒，返回 3 个可重新打开的 DOCX；最终 `package_type=uncertain`，由业务规则保留人工确认状态，不静默猜测分线。
- 追加验证：真实多卷样本（DOCX 57,847 字节、解析文本约 14,478 字符）完成多个局部分块归一化，但归并批次曾在 121 秒后返回 `ValueError`，另一次在首个归并批次达到 180 秒 `APITimeoutError`；未生成未经最终校验的 DOCX。单独重放失败分块时，7571 字符的 GLM-5 响应可成功归一化，说明失败具有 Provider 输出/时延间歇性；该次重放记录反映当时状态，后续以 2026-08-05 的用户复核更新为准。
- 复核更新（2026-08-05）：用户确认刚才归档的 Tender 分块 Change 已完成真实单卷、多卷验收；本 Change 的 5.2 复用该真实验收结论并标记完成。前端验收和通过真实 MCP 入口的人工复核分别由 5.3、5.4 承担。
- 5.3 真实 MCP 探针（2026-08-05）：通过 `http://127.0.0.1:9205/api/v1/mcp/tender/mcp` 调用 `tender.generate_bid_skeleton`，单卷结果保存在 `tmp/tender-mcp-acceptance/single-real/result.json` 并生成 1 个 DOCX，多卷结果保存在 `tmp/tender-mcp-acceptance/multi-real/result.json` 并生成 2 个 DOCX；两个结果均为 `ok`，分析分别归一化为 `single_volume`、`multi_volume`，输出 DOCX 均通过 `python-docx` 重新打开检查。业务内容仍待用户人工确认，因此 5.3 保持未勾选。
- 5.4 前端验收（2026-08-05）：用户已确认真实单卷、多卷均可在 `/agents/tender` 完成分析并生成结果；加载态防重复提交、结果展示、全部文件下载、失败重试和无 `task_id` 行为完成确认，前端不展示内部 LLM 批次。
