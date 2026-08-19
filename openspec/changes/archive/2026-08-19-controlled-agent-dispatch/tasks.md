## 1. 应用层分发契约

- [x] 1.1 新增 V2 Agent 分发命令、状态和结果模型，输入使用 `StructuredAgentCall`、可信主体和可选批准提议；完成条件：模型不暴露执行器字段并能表达授权、确认、拒绝、不可用、成功和失败状态。
- [x] 1.2 实现 Agent Call 策略校验与 Agent Runtime 的受控连接；完成条件：仅 `authorized` 调用运行时，目录重新读取且只接受 `agent` 类型和固定 `dispatch_key`。
- [x] 1.3 将运行时输出和异常映射为 `AgentCallResult`/`AgentCallError`；完成条件：非对象输出、目标缺失、输入错误和未知异常均返回稳定错误码，不泄漏内部信息。
- [x] 1.4 从 `interaction.application` 和模块入口导出新服务，并在 Composition Root 提供可替换的 Agent Runtime 注入；完成条件：生产装配使用既有 `AgentRuntime`，测试可注入替身。

## 2. 回归测试

- [x] 2.1 覆盖策略拒绝、确认缺失、目录不可用、非 Agent 和固定映射失效场景；完成条件：所有未授权分支均证明 Agent Runtime 未被调用。
- [x] 2.2 覆盖 Agent 成功对象、Pydantic 模型、非法输出、输入异常和运行时异常映射；完成条件：结果保留调用关联字段且错误消息不包含内部异常。
- [x] 2.3 覆盖单次调用、副作用和现有 V1 Gateway 回归；完成条件：全量 pytest、OpenSpec 严格校验和目标 Ruff 通过。
