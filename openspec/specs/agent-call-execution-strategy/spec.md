## Purpose

定义已授权 Agent 调用的协议无关执行策略边界，为同步运行时以及后续异步执行模式提供统一的内部扩展位置。

## Requirements

### Requirement: 已授权 Agent 调用必须通过受控执行策略

系统 MUST 在能力目录、主体权限、输入和确认策略均通过后，将结构化 Agent 调用交给由 Composition Root 注入的执行策略。执行策略 MUST 接收服务端当前目录能力和调用关联上下文，不得从客户端输入推导或覆盖执行目标。

#### Scenario: 默认同步策略完成 Agent 调用

- **WHEN** Agent 调用通过策略授权，当前目录条目仍是可用的 `agent` 能力，且 Composition Root 配置了同步执行策略
- **THEN** 系统调用一次同步执行策略
- **AND** 结果保持现有 `completed` 或受控失败语义，并关联原始 `call_id`、能力代码和运行关联字段

#### Scenario: 授权前不调用执行策略

- **WHEN** 调用缺少确认、主体无权、输入不符合目录契约、能力不可用或目录类型不是 `agent`
- **THEN** 系统返回现有受控状态和错误码
- **AND** 注入的执行策略没有被调用

### Requirement: 执行策略结果不得扩大 Agent 授权边界

执行策略 MUST 只能使用 Dispatcher 传入的服务端能力条目、固定 `dispatch_key`、标准化输入和可信主体上下文。策略返回的结果 MUST 经过现有安全结构化投影；不得把执行器对象、Provider 原始响应、异常堆栈、凭据或完整敏感输入暴露给协议调用方。

#### Scenario: 策略返回可序列化 Agent 结果

- **WHEN** 执行策略返回映射或可转换为 JSON 对象的业务结果
- **THEN** 系统将结果转换为既有 `AgentCallResult`
- **AND** 文件产物继续通过主体和会话边界暂存为安全资源引用

#### Scenario: 策略返回非法对象或抛出未受控异常

- **WHEN** 执行策略返回非对象、不可安全序列化对象或抛出未受控异常
- **THEN** 系统返回稳定错误码的 `AgentCallError`
- **AND** 不向协议调用方泄漏底层异常或原始对象

### Requirement: 执行策略契约必须保留未来延迟执行的扩展位置

系统 MUST 使用协议无关的内部执行结果边界，使后续策略可以表达已完成结果、受控失败和带 opaque execution reference 的已接收结果。TM-07.1 的默认同步策略 MUST NOT 创建 Task 或产生已接收异步结果。

#### Scenario: 当前同步策略不产生任务引用

- **WHEN** 当前能力通过默认同步策略执行
- **THEN** 系统只返回现有同步完成或失败状态
- **AND** 不创建 Task、不写入 Task 存储且不返回任务 ID

#### Scenario: 后续策略可在不修改授权流程的情况下扩展

- **WHEN** 测试注入一个符合执行策略契约的替身实现
- **THEN** Dispatcher 可以在同一套目录、权限、确认和错误边界下调用该替身
- **AND** 业务 Agent、协议适配器和 Task Domain 不需要为该替身增加直接依赖
