## 1. 策略校验服务

- [x] 1.1 新增 Agent Call 策略校验命令、状态和结果模型，保持领域调用契约与 V1 对象并存。
- [x] 1.2 实现目录、Agent 类型、权限和输入 Schema 的服务端复核，并映射稳定错误码。
- [x] 1.3 实现 `always`、`conditional`、`never` 策略分支和批准提议的能力代码、分发键、输入严格匹配。
- [x] 1.4 从 `interaction.application` 和模块入口导出服务，不接入旧 Gateway 或实际 Dispatcher。

## 2. 回归测试

- [x] 2.1 覆盖有效 Agent、非 Agent、禁用/无权限、目录异常和输入无效场景。
- [x] 2.2 覆盖确认缺失、批准匹配、能力代码/分发键/输入不匹配和 `never` 直授权场景。
- [x] 2.3 验证策略校验无执行副作用，运行 OpenSpec 严格校验、目标 Ruff 和交互回归（56 passed；依赖 PostgreSQL 的能力目录测试未纳入本次回归）。
