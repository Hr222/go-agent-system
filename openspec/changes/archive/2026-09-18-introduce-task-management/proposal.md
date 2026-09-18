## Why

Task Management 后续会跨越持久化、Worker、HTTP、业务接入和前端联调多个阶段。如果第一步没有先固定领域状态机和幂等语义，后续每个 Change 都会重新解释状态转换，最终无法稳定协作。当前先完成一个不依赖数据库、HTTP 或具体业务 Agent 的内存领域/Application 基础。

## What Changes

- 定义平台级 Task、Attempt、Event 的领域对象和状态机不变量。
- 固定 `queued`、`running`、`retry_wait`、`cancel_requested`、`succeeded`、`failed`、`cancelled` 的合法转换，以及创建、领取、取消、重试、恢复和终态提交的命令语义。
- 定义创建、领取、续租、取消、重试和成功/失败提交的幂等键、输入指纹、重复结果和冲突规则。
- 提供不依赖数据库、HTTP、Worker 或具体业务 Agent 的纯内存 Application/Domain 实现与测试。
- 同步当前架构基线，准确记录 Task Management 已实现的领域基础与尚未实施的持久化、Worker 和 HTTP 阶段。

## Capabilities

### New Capabilities

- `task-lifecycle-management`: Task、Attempt、Event 的状态机、转换和幂等领域契约。

### Modified Capabilities

- `current-architecture-baseline`: 当前架构基线明确 Task Management 已实现的领域状态机与幂等基础，同时保留后续阶段的未实施边界。

## Impact

- 新增 `app/platform/task` 的 Domain、Application 和 Ports；本 Change 不新增数据库模型、迁移、Worker 入口、HTTP 路由或前端代码。
- 本 Change 只约束领域状态和 Application 返回结果；后续持久化、Worker、HTTP、Tender、前端及 E2E Change 必须以此契约为前置依赖。
- 输入原文、租约令牌和原始异常只保留为内部领域数据，安全投影和外部协议不在本 Change 实现。
- 更新 `ARCHITECTURE.md` 的平台能力与物理目录事实，不把本 Change 描述成完整的 Task Management 交付。
