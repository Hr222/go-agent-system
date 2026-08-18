## Why

当前 Agent 能力发现只服务于运行时。统一交互入口还需要识别普通 Chat、知识库问答和政策判断，因此平台需要一份不归属任何单一 Agent 的能力目录。

## What Changes

- 新增平台级能力目录表 `platform_capability`、领域模型、查询端口和 Repository。
- 为目录项定义稳定能力代码、描述、输入输出 Schema、必填资料、确认策略、启用状态、权限、超时和固定分发键。
- 将现有 Agent 能力以目录记录方式暴露，允许非 Agent 能力以同一表结构登记。
- 通过数据库约束和应用层校验保证能力代码唯一、分发键受控、禁用能力不可被消费。
- 不做向量检索、自然语言识别、用户确认页面或自动分发。

## Capabilities

### New Capabilities

- `platform-capability-catalog`: 统一描述可由平台受控调用的 Agent 与非 Agent 能力。

### Modified Capabilities

- 无。

## Impact

- 新增 `modules/interaction` 的目录边界，并让 Agent Runtime 消费目录中的 Agent 条目。
- 新增 `platform_capability` 数据表、迁移和 Repository；不新增管理后台、HTTP 管理接口或新的 Provider。
