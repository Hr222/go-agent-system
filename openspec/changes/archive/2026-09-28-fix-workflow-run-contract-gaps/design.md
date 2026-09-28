## Context

Workflow 当前已经有固定 Version、Run/Node Run 状态机、幂等命令回执和安全事件持久化。审查发现三处运行时边界不完整：节点输入校验发生在节点开始前但没有失败事实；取消只更新领域状态，没有把请求交给执行器；依赖就绪只检查前置节点状态，未检查前置节点实际产生的安全输出引用。

本 Change 只修复固定 Workflow 契约，不引入调度器、公开入口、编辑器或多 Agent 编排。实现继续遵循 `interfaces -> Application -> Domain/Ports <- infrastructure` 的依赖方向。

## Goals / Non-Goals

**Goals:**

- 将不可重试的输入、权限和能力契约问题记录为稳定的 Node Run/Run 失败事实，并保持命令幂等。
- 通过 Node Executor Port 发出协作取消请求，让运行中的外部执行继续由执行器在安全检查点确认取消。
- 以事件中的白名单化、不透明输出引用记录节点实际可供下游消费的字段，并据此计算依赖就绪和下游输入。
- 保持公开投影不包含原始输入、文件字节、Provider 响应、凭据或可执行地址；不新增数据库表或字段。

**Non-Goals:**

- 不实现 Workflow 调度循环、自动轮询、公开 HTTP/MCP/Function Calling 入口或动态 Version 编辑。
- 不把输出引用解析为文件内容，也不让 Node Executor 直接修改 Run、Node Run 或事件。
- 不改变已有 Task 生命周期或 Tender Worker 的执行边界。

## Decisions

### 1. 用独立的输入拒绝事实表示“零尝试失败”

在 Domain 增加针对 `queued` 节点的输入拒绝转换和安全事件类型。它把 Node Run 置为 `failed`、保持 `attempt_count=0`，同时把 Run 置为 `failed` 并写入固定错误码。Application 捕获可归因于输入、权限或输出依赖的校验失败后执行该转换，并写入同一命令回执。

选择独立事件而不是伪造一次 `NODE_STARTED`，因为规格明确要求不可重试输入错误不创建执行尝试。错误消息不进入事件，只保存固定错误码。

### 2. Executor 取消端口只接收安全执行上下文

扩展 Node Executor Port，增加协作式取消方法。Application 在 Run 进入 `cancel_requested` 后，为原本处于 `running` 或 `accepted` 的节点发送包含可信主体、固定 Version/节点、命令标识和可选不透明 execution reference 的取消命令。执行器错误不被原样抛出，也不把节点伪造为 `cancelled`；Run 保持 `cancel_requested`，后续由执行器确认命令完成终态。

选择在领域状态落库后调用外部取消端口，以确保用户的取消事实不会因外部系统暂时不可用而丢失。该边界是协作请求，不提供强杀 Provider 的能力。

### 3. 通过成功事件保存不透明输出引用

节点成功时保存与 Version 输出字段一一对应的 `output_references`。事件校验字段名和引用格式，只允许白名单字段与不透明引用；不保存输出内容。`ready_nodes` 只有在前置节点成功且边引用的每个字段都存在于该前置节点最近一次成功事实中时才返回节点。Application 对边提供的输入忽略调用方伪造值，并使用已记录的安全引用；非边输入仍按节点输入契约校验。

输出引用放在已有安全事件的 JSONB 元数据中，避免增加持久化列或迁移，同时让数据库恢复后的聚合保留相同的可用输出事实。成功回放会比较输出引用，避免同一命令以不同数据流重复完成。

### 4. 兼容现有受信任回调

`complete_node` 和同步 Executor 完成结果都必须提交输出引用；没有输出字段的节点使用空映射。有输出字段但未提交完整引用时按受控执行器输出契约失败处理，不泄露异常详情。现有没有下游依赖的测试节点仅需显式提交空映射或其声明的安全引用。

## Risks / Trade-offs

- [Risk] 旧的成功事件没有输出引用 → [Mitigation] 恢复后该节点不会被视为拥有可供下游消费的输出；没有下游依赖的旧 Run 不受状态读取影响，重新执行/回写时必须补齐引用。
- [Risk] 外部执行器暂时不可用 → [Mitigation] 取消事实先落库并保持 `cancel_requested`，不伪造取消完成；执行器可在后续安全检查点重试确认。
- [Risk] 输出引用本身可能被误当成业务数据 → [Mitigation] Domain 使用不透明引用格式和字段白名单校验，事件及安全 View 不保存原始值、文件内容或 Provider 响应。

## Migration Plan

无数据库结构迁移。部署代码后，新成功事件开始携带输出引用；现有事件缺少该元数据时按“无可用下游输出”处理。回滚代码不会删除已有 JSONB 元数据，但回滚期间不应继续创建依赖新输出事实的 Workflow Run。

## Open Questions

无。真实执行器接入时仍需提供其在安全检查点消费取消命令的具体实现，但不影响本 Change 的 Domain/Application 契约。
