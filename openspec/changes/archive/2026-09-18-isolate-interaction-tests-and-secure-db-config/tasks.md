## 1. 数据库配置安全

- [x] 1.1 移除应用配置、`.env.example` 和 Docker Compose 中的数据库密码默认值；当没有 `DATABASE_URL` 时校验 `POSTGRES_PASSWORD`，并在缺失时给出明确错误。
- [x] 1.2 更新 README 的本地配置说明，明确数据库密码必须写入未跟踪的 `.env`，并补充覆盖连接串与缺少密码的配置测试。

## 2. 确认接口测试隔离

- [x] 2.1 为 Gateway 回退确认测试替换对话确认应用依赖，验证取消和确认结果都由 Gateway 返回，且不构造真实数据库依赖。

## 3. 验证

- [x] 3.1 执行相关配置与交互测试，确认无 PostgreSQL 服务时 Gateway 回退测试仍通过。
- [x] 3.2 执行 `ruff check app tests`、`python -m compileall -q app tests`、架构边界测试和 `openspec validate isolate-interaction-tests-and-secure-db-config --strict`。
