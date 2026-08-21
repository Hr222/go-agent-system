## Why

Tender Agent 已能生成投标骨架，但对话结果只展示文件元数据，页面没有可用下载入口，服务端也没有可读取生成文件的资源。用户看到“响应文件.docx”后无法取得实际产物。

## What Changes

- 将 Agent 返回的二进制文件受控暂存为服务端生成的资源，并在结果摘要中保留真实资源 ID、文件名、媒体类型和大小。
- 新增受主体与 Conversation 双重绑定的 Agent 产物下载接口；资源缺失、过期或访问上下文不匹配时不返回文件内容。
- 在聊天结果卡片中为可下载产物提供下载操作和不可用状态，不把文件字节或本地路径发送给浏览器。
- 保持现有 Tender 分析、确认和对话续写行为不变。

## Capabilities

### New Capabilities
- `agent-artifact-download`: 暂存已执行 Agent 生成的文件，并向拥有该会话访问权的主体提供受控下载。

### Modified Capabilities
- `dialogue-agent-invocation`: Agent 文件结果从仅可展示的元数据扩展为带可下载资源 ID 的安全摘要。

## Impact

- 影响 Agent 分发、产物临时存储、HTTP 路由和聊天结果组件。
- 新增一个下载 HTTP 契约和临时文件生命周期；不改变现有生成请求、确认接口或 LLM Provider 配置。
- 文件字节继续留在服务端，不进入 Conversation 事件、LLM 续写上下文或 JSON 响应。
