## Context

现有系统已经把能力目录、Agent Dispatcher、Agent→Task 桥接和 Task Worker 分成稳定边界，但没有 Workflow 运行事实。前端 `/workflow` 目前只是静态 mock；它不能成为后端契约，也不能反向要求平台直接接入动态编排框架。

本 Change 只建立平台级 Workflow 的可验证合同：一个不可变的 Workflow Version 描述有限 DAG；一次 Workflow Run 保存主体、版本、幂等键和安全状态；Node Run 保存节点级状态和受控执行引用。真正的节点执行器、公开管理接口和可视化编辑器留给后续 Change。

## Goals / Non-Goals

**Goals:**

- 定义可校验的 Workflow Definition/Version、Node、Edge、Run 和 Node Run 事实。
- 固定节点只能引用能力目录中的能力代码与服务端分发键，禁止动态地址、类名和客户端执行器选择。
- 定义 Run/Node 的状态流转、依赖就绪、幂等、取消、失败和重试语义。
- 提供受信任 Application/Port 边界，让未来执行适配器可以复用 Agent Dispatcher、Agent→Task 桥接和现有 Task Worker。
- 为 PostgreSQL 持久化保留清晰的 Repository/事件边界，并使用内存替身覆盖核心状态机。

**Non-Goals:**

- 不实现 Workflow 编辑器、版本发布 HTTP API、浏览器创建/执行入口或实时推送。
- 不实现动态 DAG 调度、并行执行器、SubAgent、多 Agent 协同或 LangGraph 集成。
- 不替换现有 Tender 外部 MCP 同步路径、Dialogue accepted 交接或 Task Worker。
- 不把 Task 结果下载、Task 终态 Conversation 回传或自然语言 Workflow 触发加入本 Change。

## Decisions

### 1. Workflow 是独立聚合，不把 Task 扩展成 Workflow

新增 `app/platform/workflow` 的 Domain、Application 和 Ports。Workflow Run 管理业务编排状态，Task 仍管理一次可租约执行；一个节点可以在未来委托给 Task，但不能把 Task 状态字段直接当作 Node Run 状态。这样取消、重试和终态回收可以分别定义，避免破坏既有 Task 不变量。

替代方案：在 `app/platform/task` 增加 `parent_run_id` 并把节点当作 Task。放弃该方案，因为会让 Task 领域承担 DAG 依赖、版本和节点输出引用，且会污染现有 Task HTTP 契约。

### 2. Definition Version 使用服务端固定注册表，运行事实持久化

Workflow Version 在 Composition Root 注册并在加载时完成节点 ID 唯一、边引用合法、无环、能力目录绑定和输入/输出引用校验；注册后的 Version 不可原地修改。Run、Node Run 和安全事件通过 Repository Port 持久化到 PostgreSQL，使用 `(workflow_version, owner, idempotency_key)` 的受控幂等依据。

替代方案：第一阶段把 Definition 和 Run 全部放在内存。放弃该方案，因为进程重启会丢失运行事实，也无法为后续 Worker 或查询提供稳定的重放边界。浏览器可编辑 Definition 则另立 Change，避免现在开放运行时注册。

### 3. Node 只表达固定能力调用，不携带可执行目标

节点使用 `capability_code` 和服务端解析后的目录绑定；创建 Run 时重新读取当前主体可用能力并校验节点输入契约。Node Executor Port 接收标准化输入、可信主体和节点上下文，返回 `completed`、`accepted` 或受控 `failed`，其中 `accepted` 只携带不透明 execution reference。具体适配器未来分别接到同步 Agent Dispatcher 或 Agent→Task 桥接，不在本 Change 注册任意运行时执行器。

替代方案：允许节点保存 Python 导入路径、HTTP URL 或用户提交的 `dispatch_key`。放弃该方案，因为它绕过能力目录、权限和 Composition 固定绑定，形成新的代码执行入口。

### 4. 依赖图决定可运行节点，状态转换由 Application 统一校验

Run 创建后节点初始为 `queued`；只有所有前置节点成功且其输出引用满足边约束时，节点才可进入 `ready`/执行边界。为减少跨模块状态，外部可观察状态只保留 `queued`、`running`、`accepted`、`succeeded`、`failed`、`cancel_requested`、`cancelled` 和 `skipped`；ready 作为 Application 查询结果，不作为持久化终态。状态转换、重试次数和取消确认使用幂等命令，不允许节点适配器直接写 Repository。

### 5. 安全投影与事件只保存最小事实

Run/Node Event 只允许版本标识、节点标识、状态、尝试序号、错误码、输入字段摘要和 execution reference 等白名单字段；不得保存原始文件、Prompt、Provider 响应、lease、凭据或完整输入。普通读取返回 owner 范围内的安全 View，含内部租约的未来执行契约只在受信任 Port 内使用。

## Risks / Trade-offs

- [固定注册表限制产品灵活配置] → 先保证契约和安全边界；可编辑 Workflow Definition 另立 Change，届时增加版本发布和授权模型。
- [节点执行适配器尚未实现] → 本 Change 只交付状态与 Port 合同，并用内存替身验证；不把 mock 伪称为真实 Workflow 执行。
- [Workflow 与 Task 双重状态] → 明确 Run/Node 与 Task 的责任边界，未来通过 execution reference 关联，不复制 Task Event。
- [依赖图校验复杂度增加] → Version 注册时一次性校验无环、边引用和能力绑定，运行时只处理已验证图。

## Migration Plan

1. 部署新增 Workflow Domain/Application、Repository 迁移和固定 Version 注册；现有 HTTP、MCP、Dialogue 与 Task Worker 不改变。
2. 旧系统没有 Workflow Run 数据，不需要数据迁移；未注册 Workflow Version 时不会影响现有能力。
3. 回滚时停止 Workflow 入口并保留已持久化的 Run 作为只读事实；不回滚或重写现有 Task/Conversation 数据。

## Open Questions

- 无。本 Change 明确不决定 Workflow 的浏览器编辑模型、并行调度策略或多 Agent/SubAgent 语义；这些将在真实产品需求明确后单独立项。
