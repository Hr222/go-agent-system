## Context

当前 Agent Management 已有 `AgentCallDispatcher`、`AgentRuntimePort` 和 `AgentRuntime`。Dispatcher 负责策略校验、当前目录复核、固定 `dispatch_key` 调用和附件结果投影；Agent Runtime 负责把固定分发键绑定到 Tender 等业务 Agent。

当前 Dispatcher 直接依赖同步 Runtime。若后续把 MCP、Task、SubAgent 或 Workflow 各自接入，会产生多个授权和结果处理入口，或者迫使 Tender 依赖 Task/Workflow。TM-07.1 只建立一个可替换的执行策略边界，默认行为保持同步，不实现后续执行模式。

## Goals / Non-Goals

**Goals:**

- 在策略授权和执行目标复核之后，增加协议无关的 Agent 执行策略 Port。
- 让当前同步 Agent Runtime 成为默认策略，并保持现有调用、错误和附件结果行为。
- 将 `StructuredAgentCall` 的关联字段传入策略，保留未来异步、父子调用和工作流关联所需的上下文。
- 让测试可以注入替身策略，验证 Dispatcher 不需要为新的执行模式复制授权逻辑。
- 保持 Composition Root 负责固定策略组装，不开放运行时动态注册或客户端指定执行器。

**Non-Goals:**

- 不迁移 Tender MCP；不改变 MCP、HTTP、Chat 的外部契约。
- 不创建 Task、Attempt、Event，不改变 Task 状态机、幂等或持久化。
- 不实现异步提交、Task Executor、SubAgent、Workflow 或 LangGraph。
- 不改变能力目录的权限、确认策略、输入 Schema 或 `dispatch_key` 语义。
- 不引入插件扫描、动态导入、远程执行地址或新的 Provider。

## Decisions

### 1. 在现有 AgentCallDispatcher 内部增加执行策略 Port

Dispatcher 继续作为唯一的 Agent 调用门面，先执行现有的目录和策略校验，再把已授权调用交给注入的执行策略。策略接收结构化调用、可信主体和当前目录能力，不能自行提升权限或重新解释客户端字段。

选择复用 Dispatcher，而不是新建平行的 `AgentBridge`，原因是现有 Dispatcher 已经统一处理授权、固定分发键、异常映射和附件资源化；平行入口会造成安全规则分叉。

### 2. 默认策略包装现有 AgentRuntimePort

Composition Root 构造一个同步策略适配器，将当前能力代码、服务端目录产生的 `dispatch_key`、标准化输入和主体权限交给 `AgentRuntimePort`。AgentRuntimePort 保持平台内部运行时边界，不向业务 Agent 暴露协议或 Task 类型。

同步策略返回现有 `completed`、受控 `failed` 等结果，Dispatcher 继续负责把结果转成 `AgentCallResult` 或 `AgentCallError`，包括附件暂存和失败补偿。

### 3. 结果契约预留延迟执行引用，但本 Change 不产生异步结果

执行策略的内部结果使用协议无关的结果类型，至少能表达已完成结果、受控失败和未来的已接收引用。TM-07.1 的默认同步策略只产生已完成或失败；`accepted`/延迟引用不映射为现有 Chat 或 MCP 响应，也不创建 Task。后续 TM-07.3 再定义异步 Task 提交和外部投影。

这样预留的是类型边界，不是提前引入 Task 领域对象或公开异步协议。

### 4. 保留调用关联字段，不提前定义父子执行语义

Dispatcher 将 `call_id`、`run_id`、`parent_run_id`、`conversation_id` 和 `turn_id` 作为不可变调用上下文传入策略。当前策略只透传这些字段到结果关联；不会写入父子树、传播取消或自动调用其他 Agent。

### 5. 仅由 Composition Root 选择策略

执行策略作为构造依赖传入。能力目录、客户端请求、模型输出和 MCP 参数都不能选择策略、覆盖执行器或提供导入路径。测试替身通过构造注入，生产绑定使用显式固定实例。

## Risks / Trade-offs

- [策略接口过早抽象] → 只抽取 Dispatcher 已经需要的最小输入、输出和上下文，不引入通用插件生命周期或工作流图模型。
- [新增中间结果类型导致状态重复] → 保持现有 `AgentCallDispatchResult` 作为协议边界；新结果只在 Dispatcher 内部使用，默认同步路径的外部状态不变。
- [策略绕过授权] → 策略只能在 Dispatcher 完成目录和 Agent Call Policy 校验后调用；测试覆盖拒绝时策略不被调用。
- [未来异步语义与当前 Chat 假设冲突] → TM-07.1 不改变 Chat 对 `completed` 的处理；异步状态和轮询/结果查询留给后续独立 Change。
- [架构依赖倒置被破坏] → Port 位于平台 Interaction/Agent Management；Tender、Task 和 interfaces 不进入该 Port 的领域契约。

## Migration Plan

1. 增加执行策略 Port 和当前同步 Runtime 适配器。
2. 调整 Dispatcher 与 Composition Root 的构造注入，保留现有调用方接口。
3. 运行现有 Agent 分发、Dialogue、附件和架构边界测试，并新增策略替身测试。
4. 如验证失败，回滚 Composition Root 的策略注入并恢复 Dispatcher 对 AgentRuntimePort 的直接适配；不需要数据库迁移或数据回滚。

## Open Questions

- TM-07.3 开始前，需要确定异步策略返回的 opaque execution reference 是否直接复用 Task ID，还是由 Agent Management 维护独立的执行引用。
- MCP 外部主体如何映射到 `RequestPrincipal` 属于 TM-07.2，不在本 Change 决定。
