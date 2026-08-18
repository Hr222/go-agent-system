## Why

现有能力候选召回已经使用目录和 Embedding 构建进程内索引，但索引由首次调用者的权限集合决定，后续查询却不携带权限。在多主体共享应用实例时，这会造成不同权限集合之间的候选缓存污染，无法作为 V2 Interaction Gateway 的可靠候选来源。

## What Changes

- 将既有能力候选索引按规范化后的权限集合隔离；索引构建、就绪检查和查询都使用同一个权限范围。
- 查询只返回当前权限范围内已启用的目录能力；未为该范围成功构建索引时，返回显式不可用结果，不复用其他范围的索引或退化为全量目录。
- 保持候选召回只输出稳定能力代码、相关性和检索元数据；不接入对话上下文、LLM 最终分类、确认提议、结构化 Agent Call 或实际分发。
- 补充跨权限范围、索引失败保留和现有政策知识隔离的回归测试。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `intent-candidate-retrieval`：候选索引与查询改为权限范围隔离，防止跨主体复用候选集合。

## Impact

- 影响 `app/modules/interaction/application/candidate_retrieval.py` 及其调用方的权限参数传递。
- 不新增数据库表、pgvector、缓存中间件、HTTP 接口或前端界面；Embedding Port 与 Platform Capability Catalog 保持既有契约。
- 后续 `interaction-proposal-confirmation` 和 Agent Call 相关 change 只能消费当前权限范围的候选，不能把召回结果当作执行授权。
