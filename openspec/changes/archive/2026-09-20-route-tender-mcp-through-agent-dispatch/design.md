## Context

当前 Tender MCP 适配器在 `app/interfaces/agent/tender_mcp.py` 中直接取得
`TenderApplication` 并调用其方法。这样 MCP 入口绕过了 Agent Management 的能力目录、
输入契约、主体权限校验和 `AgentCallDispatcher`，与对话入口形成两套执行路径。

TM-07.1 已经为 `AgentCallDispatcher` 建立了可替换的执行策略插口，但 MCP 仍使用旧的
Application 直连方式。要把 MCP 接入统一分发边界，还需要处理两个运行时约束：能力目录
需要数据库 Session，而 FastMCP Server 是长生命周期对象；Dispatcher 对二进制结果默认
进行附件暂存并只返回资源引用，而既有 MCP 契约需要返回 `EmbeddedResource` 内嵌内容。

本 Change 只改造同步 MCP 到 Dispatcher 的适配链路。Tender 仍是业务 Agent，MCP 仍是
协议适配器；Task、异步执行、Workflow、LangGraph、真实外部认证和新的 Tender 业务能力
均不属于本次设计。

## Goals / Non-Goals

**Goals:**

- 让三个现有 Tender MCP 工具都通过 `AgentCallDispatcher` 执行，并继续使用服务端能力
  目录中的固定能力代码、权限和分发键。
- 保持工具名称、公开参数、同步调用方式、结构化结果和 `EmbeddedResource` 资源表达
  兼容；MCP 客户端不需要知道内部的 `StructuredAgentCall` 或附件 ID。
- 通过 `PrincipalResolverPort` 建立协议主体边界。主体、权限和认证状态只能由服务端
  解析，客户端参数不得授予能力或权限。
- 让每次 MCP 工具调用使用短生命周期的数据库 Session、Dispatcher 和附件访问上下文，
  不把 Session 或请求状态保存在长生命周期的 MCP Server 中。
- 保留受控错误分类，不泄露异常堆栈、Provider 原文、路径、凭据或完整输入。
- 为后续执行策略、Task 或其他 Agent 组合保留 Dispatcher 边界，不在本 Change 中提前
  引入这些能力。

**Non-Goals:**

- 不创建 Task、Task 状态流转、Task ID、持久化任务记录或异步 MCP 返回。
- 不实现 MCP 外部认证协议、用户管理、Token 校验或新的主体存储；本 Change 只接入可
  替换的主体解析 Port，并在没有可信主体时拒绝受保护能力。
- 不把 Tender 提升为平台一级能力，不引入 SubAgent、Workflow、LangGraph 或新的
  `tender.fill_bid_content` 等业务功能。
- 不改变 DOCX 解析、LLM 分析、格式章节提取、边界复核和骨架渲染的业务语义。

## Decisions

### 1. MCP 通过请求级依赖作用域取得 Dispatcher

MCP Server 工厂不再接收 `TenderApplication`，而接收一个请求作用域 Provider。Provider
在每次工具调用时创建 `SessionLocal`、带该 Session 的 `ApplicationContainer` 和附件存储，
从容器取得 `AgentCallDispatcher`，调用结束后按 `try/finally` 回滚或关闭 Session，并
释放容器创建的资源。MCP Server 本身只保存 Provider，不保存 SQLAlchemy Session、目录
对象或某次调用的附件内容。

Provider 的契约放在协议适配边界，以 `contextmanager` 或等价的 `McpDispatchScope`
表达，至少提供 Dispatcher 和同一主体上下文下的 `AttachmentReadPort`。MCP 适配器不
导入 SQLAlchemy、Repository 或数据库 URL；数据库连接和对象图组装仍由 Composition
Root 负责。

选择请求级作用域而不是复用进程级 Dispatcher，是因为 `SessionScopedCapabilityCatalog`
必须在目录读取时打开短 Session，且附件资源的 owner 校验也必须与当前调用主体一致。
若目录或数据库不可用，作用域返回受控的 `CAPABILITY_CATALOG_UNAVAILABLE`，不让底层
异常穿过 MCP 边界。

### 2. 主体解析复用协议中立的 Security Port

工具函数通过 FastMCP 的请求 Context 取得当前请求可见的 headers，并构造
`PrincipalResolutionContext` 交给注入的 `PrincipalResolverPort`。MCP 适配器只负责把
协议请求转换成中立的 headers 映射，不解析权限 Header，也不接受工具参数中的
`subject`、`permissions`、`capability_code` 或 `dispatch_key`。

本 Change 的默认组装复用现有服务端主体模式：受控部署可使用配置的
`StaticPrincipalResolver`，匿名模式解析为 `RequestPrincipal.anonymous()`。匿名主体不
满足 `agent:tender:execute` 时由 Dispatcher 拒绝调用；不能为了兼容旧 MCP 客户端而把
匿名请求升级成有权限主体。真正的 Token、OAuth 或客户端证书解析留给后续 Security
Change。

### 3. MCP 使用服务端固定的工具到能力映射

适配器维护不可由客户端覆盖的静态映射：

| MCP 工具 | Agent 能力代码 | 固定分发键 |
| --- | --- | --- |
| `tender.generate_bid_skeleton` | `tender.generate_bid_skeleton` | `agent.tender.generate_bid_skeleton` |
| `tender.extract_bid_format_section` | `tender.extract_bid_format_section` | `agent.tender.extract_bid_format_section` |
| `tender.verify_extraction_boundary` | `tender.verify_extraction_boundary` | `agent.tender.verify_extraction_boundary` |

适配器只把固定能力代码和已组装的输入放入 `StructuredAgentCall`；Dispatcher 再从当前
目录读取能力并使用目录中的 `dispatch_key`。即使 MCP 请求携带同名或不同名的扩展字段，
也必须忽略，不能形成动态执行地址。

每次 MCP 调用生成新的 `call_id` 和 `run_id`（使用服务端 UUID/hex 标识）；
`conversation_id`、`turn_id` 和 `parent_run_id` 默认保持 `None`。MCP 请求 ID 只可用作
日志关联信息，不能伪装成 Conversation 或 SubAgent 父子关系。

### 4. 公开 Base64 输入先转为受控附件，再进入能力输入

MCP 的公开字段继续是 `file_name`、`content_base64` 及现有工具的其他字段。适配器负责
Base64 严格解码、空内容和大小限制的早期校验，然后通过 `AttachmentStoragePort` 在当前
主体和请求作用域下暂存输入，并使用 `ResolvedAttachment` 组装内部的
`source_document`。这样能力策略校验看到的是目录声明的服务端附件类型，而不是可以被
模型或客户端伪造的本地路径、URL 或任意 bytes 字段。

三个 Tender 能力的目录输入契约统一声明 `source_document` 的 DOCX 附件约束；对外的
MCP 参数不变。Runtime 的 Tender 适配函数支持该内部输入并仍可保留旧的 Base64 分支，
以兼容对话入口或已有内部测试。输入附件只在本次调用使用，成功或失败后由作用域按
现有附件清理策略处理。

该决定也避免了让 Dispatcher 看到不符合目录 Schema 的 `content_base64`：能力目录仍是
唯一输入契约来源，MCP 只是把协议字段转换为已验证的内部附件值。

### 5. 二进制输出通过 Attachment Port 取回并投影为 MCP 资源

Dispatcher 继续执行统一的安全结果投影，将 Tender 结果中的二进制 artifact 暂存到
Attachment Storage，并在 `AgentCallResult.output` 中返回不含 bytes 的 `resource_id`、
文件名、媒体类型和大小。MCP 适配器不得直接访问文件系统；它使用同一请求主体和附件
访问上下文通过 `AttachmentReadPort` 读取这些资源，再构造现有 `BlobResourceContents`
和 `EmbeddedResource`。

文本分析、边界上下文和文件元数据从 Dispatcher 输出投影；资源 URI 仍使用现有
`tender://artifacts/<safe-name>` 形式。读取失败返回受控的资源投影错误，并不泄露本地
路径或附件内部实现。读取完成后按当前临时附件策略清理，避免 MCP 响应之外留下不可回收
的中间文件。

选择“Dispatcher 暂存、MCP 读取”而不是让 MCP 绕过暂存直接嵌入 bytes，是为了复用统一
的输出安全、owner 隔离和失败清理规则；选择 Attachment Port 而不是文件系统 API，是
为了保持 Interfaces -> Application/Port 的依赖方向。

### 6. 受控错误由执行边界产生，MCP 只做协议映射

Dispatcher 的策略、目录、输入、目标不可用、运行失败、输出非法和附件保存错误继续
使用统一错误码。为保持 Tender 现有错误分类，Tender 的 Composition 适配层把已知业务
异常（输入、DOCX 解析、模型未配置、上游失败、分析结果无效、渲染失败）转换成
`AgentExecutionOutcome.failed` 的稳定错误码和安全消息；平台 Dispatcher 不直接依赖
Tender 异常类型。未知异常统一转换为通用执行失败。

MCP 根据 Dispatcher 错误和资源读取结果映射到现有的 `INVALID_INPUT`、
`DOCUMENT_PARSE_FAILED`、`SERVICE_NOT_CONFIGURED`、`UPSTREAM_FAILED`、
`ANALYSIS_FAILED`、`RENDER_FAILED`、`INTERNAL_ERROR` 或对应的受控平台错误。映射表是
协议适配代码的一部分，错误消息固定且不包含异常原文；新增执行策略只能返回受控错误
结构，不能把异常堆栈带回 MCP。

### 7. 同步执行保持现状，未来策略沿用同一入口

TM-07.2 只使用 TM-07.1 已存在的同步执行策略。Dispatcher 返回 `completed` 或受控
失败；MCP 不处理 `accepted`、执行引用或 Task 查询。未来异步策略可以在同一 Dispatcher
和主体/目录边界下增加协议能力，但必须由新的 Change 明确定义返回契约。

## Risks / Trade-offs

- **[匿名 MCP 客户端全部被拒绝]** → 这是受保护 Tender 能力的安全预期；受控部署通过
  `REQUEST_PRINCIPAL_MODE=static` 和服务端权限配置启用，真实认证另行设计。
- **[每次调用创建数据库 Session 增加连接开销]** → Session 只覆盖一次目录、执行和
  结果投影，使用现有连接池和 `finally` 关闭；不把 Session 留在 MCP 长生命周期对象中。
- **[附件暂存后再读取会增加磁盘和一次读取]** → 换取统一的大小、媒体类型、owner
  隔离和清理语义；失败时由 Dispatcher/作用域清理已暂存资源。
- **[目录元数据和旧 SQL 种子可能不一致]** → 以能力目录的
  `source_document` 声明为准，增加幂等的目录元数据更新并补充迁移/架构测试；MCP
  公开字段不变。
- **[旧的具体 Tender 错误码可能在统一 Dispatcher 中丢失]** → 在 Composition 的
  Tender 执行适配层产生 `AgentExecutionOutcome.failed` 的安全错误码，Dispatcher 和
  MCP 只传递受控结果；未知异常接受通用错误。
- **[FastMCP 请求 Context 在框架升级后变化]** → 将 Context 到
  `PrincipalResolutionContext` 的转换封装在 MCP 接口小适配器中，并用协议级测试覆盖
  headers、匿名主体和静态主体路径。

## Migration Plan

1. 先补齐本 Change 的能力契约和设计对应的架构/协议测试，确认三个 MCP 工具的公开
   Schema 与旧版本一致。
2. 增加请求级 MCP 依赖作用域、Principal Resolver 注入和固定工具映射；将工具实现改为
   构造 `StructuredAgentCall` 并调用 Dispatcher。
3. 更新 Tender Runtime 适配和能力目录元数据，使三个能力接受服务端解析的
   `source_document`，同时保留需要的内部兼容分支。
4. 增加输出资源读取投影、稳定错误映射、匿名拒绝、权限通过、目录不可用、输入非法和
   三个工具成功路径的单元/协议测试。
5. 执行相关 pytest、架构边界测试、`openspec validate --strict` 和 `git diff --check`。
   只有验证通过并完成人工审阅后，才按仓库流程归档、提交和推送。

回滚时恢复 MCP Server 的旧 Application Provider 和旧测试装配即可；本 Change 不新增
数据库表、Task 数据或不可逆数据迁移。若能力目录元数据更新已经部署，回滚代码前应保留
`source_document` 声明，因为它是服务端内部输入约束的兼容扩展，不改变 MCP 公开字段。

## Open Questions

- FastMCP 当前版本传入的请求对象是否在所有部署模式都提供完整 headers；若某些模式不
  提供，是否由部署层注入一个明确的可信主体上下文，而不是回退到客户端参数。
- Tender 三项能力的目录元数据由现有 SQL 种子更新，还是通过既有能力管理迁移脚本
  更新；需要在实现 Change 时结合当前部署数据库确认幂等执行方式。
- MCP 内嵌资源的大小是否应继续受单次响应上限约束；若超过上限，应由后续 Change 定义
  MCP 资源引用/下载契约，本 Change 暂不改变现有同步返回。
- 静态主体权限配置是否应在默认开发环境示例中包含 `agent:tender:execute`；实现时需
  与当前 `.env.example` 和安全文档保持一致，不能把生产权限写死进代码。
