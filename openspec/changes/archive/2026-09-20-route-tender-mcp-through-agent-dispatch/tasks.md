## 1. 请求作用域与安全主体

- [x] 1.1 增加 MCP 请求级分发作用域契约，能够在一次工具调用内提供 `AgentCallDispatcher`、附件 Port 和可信 `RequestPrincipal`，并保证 Session、容器和临时资源在成功与异常分支关闭；完成条件：作用域不持有跨请求 Session，匿名主体不会被升级为有权限主体。
- [x] 1.2 更新 Composition Root 与 MCP 挂载组装，使用短生命周期数据库 Session 构造 Dispatcher，并注入服务端配置的 `PrincipalResolverPort`；完成条件：MCP Server 工厂不再接收 `TenderApplication`，且不直接依赖 SQLAlchemy、Repository 或 Provider SDK。

## 2. Dispatcher 输入与结果边界

- [x] 2.1 为 MCP 三个工具建立服务端固定能力映射、调用关联标识和 Base64/文件约束校验；完成条件：客户端不能覆盖能力代码、权限或分发键，非法输入在 Dispatcher/Agent 执行前被拒绝。
- [x] 2.2 调整 Tender Agent 适配与能力目录输入契约，使 MCP 输入能够转换为受控的 `ResolvedAttachment` 或现有兼容字段；完成条件：Tender Application 仍只接收业务 Command，目录输入校验和主体附件访问约束有效。
- [x] 2.3 增加 Dispatcher 结果到 MCP `EmbeddedResource` 的安全投影，使用 Attachment Port 读取二进制资源并映射受控错误；完成条件：MCP 不直接读文件系统、不泄露 `resource_id` 或异常原文，并清理中间附件。

## 3. Tender MCP 迁移

- [x] 3.1 将 `tender.generate_bid_skeleton`、`tender.extract_bid_format_section` 和 `tender.verify_extraction_boundary` 改为统一构造 `StructuredAgentCall` 并调用 Dispatcher；完成条件：三个工具不再直接调用 `TenderApplication`，名称、公开 Schema、同步返回和业务结果保持兼容。
- [x] 3.2 实现 Dispatcher 状态与 Tender 业务错误到稳定 MCP 错误的映射；完成条件：主体不足、目录不可用、输入无效、DOCX 解析、模型配置、上游、分析和渲染失败均不泄露内部细节。

## 4. 验证与边界回归

- [x] 4.1 更新 MCP Adapter 与协议测试，覆盖工具发现、三工具成功调用、匿名/无权限拒绝、伪造授权字段、非法 Base64、目录/运行时失败和 EmbeddedResource 返回；完成条件：相关 pytest 全部通过。
- [x] 4.2 增加或更新 Dispatcher、Composition 和架构边界测试，确认一次调用最多执行一次、无 Task/Conversation 持久化、Session 关闭和接口层无越层依赖；完成条件：相关 pytest、架构测试、`openspec validate --strict` 和 `git diff --check` 通过。
