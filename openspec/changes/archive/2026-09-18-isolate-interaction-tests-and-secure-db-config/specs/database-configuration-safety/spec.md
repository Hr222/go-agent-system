## ADDED Requirements

### Requirement: 数据库凭据必须显式配置
系统 SHALL 不在受版本控制的应用配置、示例环境文件或 Docker Compose 中提供数据库密码默认值。系统 SHALL 优先使用非空的 `DATABASE_URL`；未提供该值时，构造数据库连接串 MUST 要求非空的 `POSTGRES_PASSWORD`，并在缺少时给出指出该配置项的错误。

#### Scenario: 使用完整连接串
- **WHEN** 运行环境提供非空 `DATABASE_URL`
- **THEN** 系统使用该连接串
- **AND** 系统不要求单独的 `POSTGRES_PASSWORD`

#### Scenario: 缺少分项密码
- **WHEN** `DATABASE_URL` 为空且 `POSTGRES_PASSWORD` 为空
- **THEN** 系统拒绝构造数据库连接串
- **AND** 错误信息指出需要配置 `POSTGRES_PASSWORD` 或 `DATABASE_URL`

#### Scenario: 从示例配置启动数据库
- **WHEN** 开发者未在本地 `.env` 中设置 `POSTGRES_PASSWORD` 就启动 PostgreSQL Compose
- **THEN** Compose 在创建数据库容器前失败
- **AND** 失败信息指出缺少 `POSTGRES_PASSWORD`
