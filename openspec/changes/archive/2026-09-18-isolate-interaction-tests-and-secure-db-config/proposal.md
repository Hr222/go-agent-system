## Why

确认接口的回归测试只替换了 Gateway，仍会构造对话确认应用并访问本地 PostgreSQL，导致测试结果依赖开发机服务状态。与此同时，仓库配置和示例配置中包含数据库密码默认值，不符合不得提交数据库凭据的约束。

## What Changes

- 让确认接口的 Gateway 回退分支测试替换全部路由依赖，验证时不建立真实数据库连接。
- 移除应用配置、示例环境文件和 Docker Compose 中的数据库密码默认值。
- 在生成数据库连接串前明确要求 `DATABASE_URL`，或完整的 `POSTGRES_*` 连接配置；缺少密码时返回可操作的配置错误。
- 更新本地启动说明，要求开发者在未提交的 `.env` 中设置数据库密码。

## Capabilities

### New Capabilities

- `database-configuration-safety`: 数据库连接配置不包含提交到仓库的密码，并在缺少必要凭据时给出明确错误。
- `hermetic-interaction-route-tests`: 确认接口的 Gateway 回退分支使用稳定替身，不依赖本地 PostgreSQL。

### Modified Capabilities

- 无。

## Impact

- 受影响代码：`app/shared/config.py`、数据库 Docker Compose、确认接口测试及配置测试。
- HTTP 响应和持久化模型不变；本地首次启动需要在 `.env` 中提供数据库密码，或设置完整的 `DATABASE_URL`。
- 不涉及外部 Provider、业务状态流转或数据库迁移。
