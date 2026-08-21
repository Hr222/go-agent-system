## Why

旧的 `POST /api/v1/agents/tender/skeleton` 可直接执行 Tender Application，既不解析可信主体，也不经过能力目录、显式确认和 Dialogue 调用记录。它还将生成文件以 Base64 放入 HTTP JSON，与当前 Agent 产物的受控下载契约相冲突。

当前 Chat 已具备上传附件、受控识别、确认、Agent 调用和资源下载闭环。需要退场旧浏览器入口，避免同一业务能力存在两套安全和文件交付语义。

## What Changes

- **BREAKING** 移除浏览器可调用的 `POST /api/v1/agents/tender/skeleton` 同步生成接口及其 Base64 文件响应。
- 移除 Tender 前端页面对该旧接口和 Base64 下载的依赖；页面只提供进入现有受控对话入口的导航。
- 保留 Tender Application、Agent Runtime、MCP 协议适配器和 Chat 中的已授权 Tender 调用，不改变其输入分析、确认策略或受控下载接口。
- 为已退场 HTTP 路由和 Tender 页面补充回归测试，避免再次引入未经受控分发的浏览器 Agent 执行入口。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `tender-agent-skeleton`: 浏览器不再使用旧同步 HTTP 入口执行或获取 Tender 生成产物；文件交付统一走已授权对话调用的安全资源摘要与下载接口。
- `agent-artifact-download`: 浏览器可下载的 Agent 文件资源只从受控对话 Agent 调用产生，不能由旧 Tender Base64 HTTP 响应替代。

## Impact

- 删除 `app/interfaces/http/routes/tender.py` 的路由注册和旧 HTTP Schema/测试引用。
- 调整 `frontend/src/features/agent/tender/` 页面与 API 调用，取消 Base64 文件解码。
- 不涉及数据库迁移、模型 Provider、MCP 文件资源协议或 Conversation 持久化格式。
