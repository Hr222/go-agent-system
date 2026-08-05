## Why

当前 Tender Agent 把解析后的整份招标文本一次性提交给结构化 LLM。实际测试表明，5MB～7MB 的 DOCX 也可能展开为数万字符，并在 GLM 上游等待超时；不同 Provider 的名义上下文窗口不能作为系统稳定性的前提。V1 需要把文档拆成受控大小的证据片段，再汇总为同一份投标分析结果。

## What Changes

- 为 Tender Application 增加请求级文档索引和语义分块流程，按章节、表格和证据边界组织输入。
- 为每个分块执行受控的要求提取，只输出要求、分线候选、证据引用和待确认项等紧凑中间结果。
- 增加全局归并阶段，统一处理去重、冲突、单卷/多卷判断、服务交付成果区分和最终 `TenderAnalysis` Schema 校验。
- 规定 50MB 以内的 DOCX 也统一走分块路径，不再把文件大小范围内的文档直接作为一次 LLM 输入。
- 保持 `tender.generate_bid_skeleton` 的 HTTP、MCP 输入输出契约和骨架文件结果兼容；分块过程不对外暴露为 SubAgent 或新任务。
- 增加单块超时、有限重试、失败分块和待确认项的稳定错误与诊断信息，不记录原始招标文本、用户关注点或生成内容。
- 设置 70MB 的服务端绝对拒绝线；50MB 以上不作为 V1 正常分析范围，具体边界策略由实现配置明确，不承诺大文件成功分析。

## Capabilities

### New Capabilities

- `tender-agent-chunked-analysis`: 定义招标文档证据索引、分块提取、全局归并、预算控制和可追溯分析结果。

### Modified Capabilities

- 无。现有 `tender-agent-skeleton` 尚未同步为主规格；本 Change 通过新增能力约束其内部分析流程，并保持已实现的外部 HTTP/MCP 契约兼容。

## Impact

- 影响 `app/modules/agent/tender` 的 Application 编排、文档 Port 契约和 Structured LLM 适配器；需要增加分块计划、中间结果和归并结果模型。
- 影响 DOCX Reader 的证据块元数据和输入预算统计，但不改变骨架 Renderer 的输出契约。
- HTTP 和 MCP 不新增调用步骤、不创建 `task_id`、不引入持久化；同步调用的总耗时和 LLM 调用次数会增加。
- 不接入公司知识库、V2 内容填充、异步任务管理、断点恢复、100MB 以上文件传输或 SubAgent Runtime。
- 外部 Provider 只需支持受控大小的结构化 JSON 请求；系统不依赖 Provider 的附件上传或超大上下文能力。
