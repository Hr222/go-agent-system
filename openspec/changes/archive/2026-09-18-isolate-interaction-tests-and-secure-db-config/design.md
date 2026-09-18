## Context

确认接口同时注入对话确认应用和 Gateway。前者先处理已绑定会话的 Agent 提议，返回 `None` 时才回退到 Gateway；这是现有 HTTP 契约的一部分。现有 Gateway 回退测试只替换后者，使依赖解析构造前者并间接访问 PostgreSQL。

数据库密码同时出现在 `Settings` 默认值、`.env.example` 和 Docker Compose 的回退表达式中。项目约定禁止提交数据库凭据，但本地配置仍需支持 `DATABASE_URL` 或分项 PostgreSQL 配置。

## Goals / Non-Goals

**Goals:**

- 使 Gateway 回退确认测试完全由替身驱动，不访问本地数据库。
- 从受版本控制的配置文件中移除数据库密码。
- 缺少连接凭据时，在构造数据库 URL 或启动 Compose 时提供可操作的失败信息。
- 保持现有确认接口、数据库表结构和生产组装方式不变。

**Non-Goals:**

- 不改造确认接口的双分支处理逻辑。
- 不修改 PostgreSQL 用户、数据库名、端口或已有数据。
- 不引入密钥管理服务、运行时配置中心或数据库迁移。

## Decisions

### 确认路由测试替换两个依赖

Gateway 回退测试将替换对话确认应用和 Gateway。对话替身的 `confirm_agent` 异步返回 `None`，显式覆盖“未绑定对话 Agent，继续 Gateway 回退”的分支。

保留路由的现有依赖注入。删除对话确认应用依赖或在路由内按条件延迟构造，会改变已绑定会话 Agent 的确认路径，且无法解决测试遗漏依赖的问题。

### 数据库密码没有默认值

`POSTGRES_PASSWORD` 采用空值默认，并在 `database_url` 未收到非空 `DATABASE_URL` 时验证该字段。非空 `DATABASE_URL` 保持优先级最高，允许由部署环境使用统一连接串。

不使用新的固定“开发密码”替代旧默认值。任何版本控制中的回退密码都会重新引入同类风险。测试在其隔离环境中提供合成密码，不将其作为应用配置默认值。

### 示例和 Compose 早失败

`.env.example` 只保留空的 `POSTGRES_PASSWORD` 并说明必须在本地 `.env` 填写。Docker Compose 对密码使用必填变量表达式，使首次启动在创建容器前失败，而不是以意外的共享默认密码启动。

## Risks / Trade-offs

- [首次复制示例配置后启动失败] → README 和 Compose 错误信息明确指出需要设置 `POSTGRES_PASSWORD` 或 `DATABASE_URL`。
- [测试环境未注入密码而在导入时构造数据库引擎] → 测试初始化提供合成配置；不发起网络连接的单元测试仍不需要数据库服务。
- [误把测试替身当作生产行为] → 替身只用于断言 Gateway 回退，已绑定对话 Agent 的现有测试继续覆盖其优先分支。

## Migration Plan

1. 开发者在未跟踪的 `.env` 中设置新的本地数据库密码，或提供完整 `DATABASE_URL`。
2. 使用同一密码启动 Docker Compose 和后端；已有数据库卷不执行自动迁移。
3. 若需回滚代码，可恢复旧版本；本地密码保留在 `.env`，不需要回滚数据。

## Open Questions

- 无。
