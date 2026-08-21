## MODIFIED Requirements

### Requirement: Tender 文件结果只能以安全且可下载的资源摘要进入事件

系统 MUST 将 Tender Agent 返回的文件对象投影为文件名、媒体类型、大小和服务端资源标识等 JSON 元数据。对成功暂存的产物，该资源标识 MUST 可与当前主体和 Conversation 一同用于受控下载。系统 MUST NOT 将文件原始字节、Provider 响应或执行器对象写入 Conversation 事件或 HTTP JSON 响应。

#### Scenario: Agent 返回包含文件的结果

- **WHEN** Tender Agent 返回分析结果和一个或多个已成功暂存的生成文件
- **THEN** 事件保存分析摘要与每个文件的安全元数据和资源标识
- **AND** 页面可以显示文件名、类型和大小，并为该会话提供下载操作

#### Scenario: Agent 结果无法安全投影

- **WHEN** Agent 返回不可序列化对象、不符合白名单结构，或文件未能完成受控暂存
- **THEN** 系统返回 `AGENT_OUTPUT_INVALID` 或 `AGENT_ARTIFACT_STORE_FAILED`
- **AND** 不持久化原始对象、二进制内容或不可用资源标识
