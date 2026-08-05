## 1. Provider 配置与 Client Factory

- [x] 1.1 增加 DeepSeek Provider 配置，包括 API Key、Base URL、模型、超时、最大输出和 thinking 选项；保留现有 `ZHIPU_*` 配置，默认行为继续使用 GLM。
- [x] 1.2 将 `OpenAICompatibleClientFactory` 的 Client 创建逻辑改为使用解析后的 Provider 配置；完成条件：DeepSeek 和 GLM 都能创建各自的 Client，缓存、超时、API Key 缺失错误和脱敏日志行为有回归测试。

## 2. DeepSeek Adapter 与 Composition Root

- [x] 2.1 实现 DeepSeek Chat/Streaming Adapter，使其实现现有 `ChatLlmPort` 和 `StreamingChatLlmPort` 契约；完成条件：普通 Chat 的 `ChatLlmResult`、模型元数据、Token 元数据和错误映射保持现有行为。
- [x] 2.2 实现 DeepSeek Structured Adapter；完成条件：请求发送 `response_format={"type":"json_object"}`、关闭 V4-Flash thinking，并通过现有 `RawStructuredLlmResponse`、装饰层和 `StructuredLlmResult` 返回直接 JSON Schema 结果，不新增 DeepSeek 专用字段转换。
- [x] 2.3 在 Composition Root 中增加 Provider 选择；完成条件：DeepSeek 配置组装 DeepSeek Adapter，GLM 配置仍组装现有 GLM Adapter，Tender 和 Chat Application 不出现 Provider 名称分支。

## 3. Provider-neutral MVP 脚本

- [x] 3.1 将 LLM 网络/普通 Chat/JSON 诊断脚本改为通过 Provider 配置运行；完成条件：脚本可以选择 GLM 或 DeepSeek，输出网络状态、模型、响应格式、耗时和响应长度，不输出 API Key、完整 Prompt 或完整响应。
- [x] 3.2 将单块 Tender smoke 改为调用 Provider-neutral Structured Port；完成条件：脚本不直接实例化 GLM Adapter，DeepSeek 返回结果通过 `TenderChunkAnalysis` 本地校验，并明确不代表全局归并或 DOCX 验收。

## 4. 自动化回归验证

- [x] 4.1 增加 DeepSeek Factory、Chat/Streaming Adapter 和 Structured Adapter 的 Fake 响应测试；覆盖角色映射、JSON Object 请求、thinking 参数、直接 JSON、`reasoning_content` 隔离和上游失败。
- [x] 4.2 增加 Composition Root 和架构边界回归测试；完成条件：两个 Provider 均可组装，现有 LLM Port/Result 和 GLM 测试保持通过，Application/Domain/HTTP/MCP 不依赖具体 DeepSeek Adapter。
- [x] 4.3 增加不兼容返回的失败闭合测试；覆盖空响应、无效 JSON、字段类型错误，并确认没有字段猜测、静默丢字段或二次 LLM 修复。

## 5. 真实 MVP 验收与交付记录

- [x] 5.1 使用可用 DeepSeek 配置运行网络、普通 Chat 和 JSON Object MVP smoke；完成条件：记录 Provider、模型、输入规模、响应格式、耗时和脱敏成功/失败原因。
- [x] 5.2 使用 DeepSeek V4-Flash 运行单块 Tender Structured smoke；完成条件：取得真实 `TenderChunkAnalysis` 或记录结构化失败诊断，不记录 API Key、完整 Prompt、完整响应或招标正文。
- [x] 5.3 执行目标测试、`ruff check app tests`、`python -m compileall -q app tests` 和 OpenSpec strict validation，并将验证结果写入 Change 文档；不宣称完成 Tender 全局归并、多卷验收或 DOCX 业务交付。
