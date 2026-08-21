## Context

浏览器仍可通过 `POST /api/v1/agents/tender/skeleton` 直接调用 Tender Application。该路由不解析 `RequestPrincipal`，也不经过 Interaction 的能力目录、确认和 Dialogue Agent 调用记录；它将 DOCX 产物编码为 Base64 JSON。与此同时，Chat 已提供受主体与会话约束的 Tender 调用和下载资源链路。

此 Change 只收敛浏览器入口。MCP 是外部 Agent 协议适配器，仍按其协议返回资源内容，不使用浏览器 HTTP JSON 契约。

## Goals / Non-Goals

**Goals:**

- 让浏览器无法再通过旧同步接口绕过可信主体、能力授权和显式确认。
- 让浏览器端 Tender 文件交付只依赖受控对话结果的资源摘要和下载接口。
- 保留 `/agents/tender` 的稳定导航入口，同时不再让该页面提交原始文件或处理 Base64 文件内容。

**Non-Goals:**

- 不修改 Tender Application、DOCX 解析、渲染、MCP 工具或模型调用。
- 不新增真实认证、会话 owner 隔离、任务队列或长期文件归档。
- 不在本 Change 重建一个与 Chat 重复的 Tender 对话页面。

## Decisions

### 删除旧浏览器同步路由

从 HTTP router 移除 Tender V1 路由，因此旧 `POST /api/v1/agents/tender/skeleton` 返回标准路由不存在响应，且不会执行 Tender Application。选择删除而非保留兼容响应，是为了避免浏览器调用者继续依赖一个无法满足当前安全和文件交付契约的接口。

替代方案是在旧路由内补充主体校验和临时资源暂存。这仍会创建第二套绕过 Interaction 授权、确认和 Conversation 记录的 Agent 执行路径，因此不采用。

### Tender 页面只进入受控对话

`/agents/tender` 保留为 Agent 导航入口，但不再提交 multipart 文件、调用旧 API 或解码 Base64。页面仅提供进入 `/chat` 的明确操作；实际请求使用既有通用附件组件和对话确认流程。

选择复用已有 Chat 闭环，而不在本 Change 把相同的上传、确认、状态和下载状态复制到 Tender 页面。专属 Tender 工作台的任务状态和结果预览需要单独设计。

### MCP 不纳入浏览器退场

MCP 工具通过协议资源块传递二进制，是外部 Agent 协议语义，不是浏览器 JSON API。该路径继续调用 Tender Application，但本 Change 不增加浏览器可访问的 MCP 文件下载能力。

## Risks / Trade-offs

- [依赖旧 `/agents/tender/skeleton` 的浏览器客户端会收到 404] → 这是有意的破坏性退场；迁移目标是 `/chat` 的受控对话链路。
- [Tender 页面暂时不再提供独立表单] → 保留页面与导航，后续专属任务体验通过独立 Change 实现。
- [MCP 仍能获取文件内容] → MCP 不是浏览器入口；后续若引入外部主体认证，另行设计 MCP 身份与资源授权。

## Migration Plan

1. 发布时移除旧路由和前端直连接口。
2. 用户在 `/agents/tender` 进入 `/chat`，上传 DOCX 并确认系统生成的 Tender 提议。
3. 已发布的前端不再发送旧请求；外部旧客户端需迁移后再升级。
4. 回滚时恢复路由和前端 API，但会重新引入未受控的文件交付风险，不能作为常规回滚方案。

## Open Questions

无。专属 Tender 工作台的受控调用体验留给后续独立 Change。
