## Why

TM-07.1 已为 Agent 调用保留协议无关的延迟执行结果，TM-07.2 也已将 Tender MCP 统一到受控 Agent 分发边界；但当前 `accepted` 只是执行策略的内部占位，目录能力还没有安全、可审计的异步 Task 提交契约。若由调用方直接创建 Task，会绕过能力授权、固定执行器和主体归属，也会使重试重复创建任务。

本 Change 为后续业务 Agent 接入异步执行提供平台级桥接边界：只有服务端登记为异步能力的目录条目可以进入桥接，桥接通过既有受信任 Task 提交能力创建固定策略的 Task，并返回稳定的任务执行引用。它不实现 Tender 的异步 Consumer，也不开放通用 Task 创建接口。

## What Changes

- 增加通用的 Agent Call 到 Task 的受控桥接 Application 契约。
- 为已登记目录能力增加服务端控制的异步资格与固定 Task 提交档案绑定；调用输入中的同名字段不得被解释为或覆盖 task type、executor、owner、重试策略或展示字段。
- 在 Dispatcher 已完成目录、主体、输入和确认复核后，允许异步资格能力交给桥接执行；普通同步能力仍保持一次同步执行且不创建 Task。
- 使用可信调用关联和标准化输入快照生成稳定幂等键与输入指纹；同一异步调用重放返回原 Task 引用，不创建重复 Task，冲突输入返回稳定错误。
- 通过既有 `TrustedTaskSubmissionService` 写入 Task，并将安全提交结果转换为不含输入指纹、lease 或原始输入的 opaque execution reference。
- 明确失败、未配置、目录失效和不满足异步资格时的受控结果；桥接不得直接访问 Repository、数据库或公开协议层。
- 预留后续业务 Consumer、取消/重试和结果资源映射所需的扩展插口，但不在本 Change 实现 Tender、Workflow、Subagent 或前端联调。

## Capabilities

### New Capabilities

- `agent-task-bridge`: 定义经授权的 Agent Call 如何按服务端异步档案受控提交为 Task、保持幂等并返回执行引用。

### Modified Capabilities

- `agent-call-execution-strategy`: 补充异步策略必须通过受控桥接提交 Task、使用安全引用且不得开放通用创建的行为约束。

## Impact

- 影响 Agent Management 的目录模型、Dispatcher/执行策略契约和 Composition 绑定方式。
- 复用 `app/platform/task` 的受信任提交 Application，不改变 Task 状态机、Worker、HTTP 管理接口或公开创建边界。
- 可能新增 Agent/Task 之间的 Application Port、固定异步档案注册和输入快照/指纹工具；不新增 HTTP、MCP 或浏览器路由。
- 持久化沿用既有 Task 幂等唯一键和安全投影，不保存原始 Agent 输入、凭据、lease 或 Provider 响应。
- 后续 TM-07.4 将使用本 Change 的插口配置 Tender 异步能力；本 Change 本身不绑定 Tender。
