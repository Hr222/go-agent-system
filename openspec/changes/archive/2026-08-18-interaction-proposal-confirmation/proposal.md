## Why

P2.2 只能为当前主体缩小能力候选范围，仍不能让候选或识别结果获得执行权。V2 需要一个独立的确认核心：只有目录策略要求确认且输入已通过服务端校验时，才能生成短期、主体绑定、一次性消费的待确认提议。

## What Changes

- 明确 `ExplicitCapabilityConfirmation` 只为确认策略为 `always` 或当前按 `always` 处理的 `conditional` 能力创建提议；`never` 条目不进入确认流程。
- 强化内存待确认提议存储：保存和取回均使用服务端快照，保留短 TTL、主体绑定和原子单次消费语义。
- 固化确认层边界：确认或取消只返回受控确认结果，不在确认服务或存储中执行 Agent、LLM、RAG 或其他 Use Case。
- 补充确认策略、对象快照、过期、主体不匹配和重复消费的回归测试。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `explicit-capability-confirmation`：补充策略门控和服务端短期提议快照的安全语义。

## Impact

- 影响 `app/modules/interaction/application/confirmation.py`、内存提议存储和交互测试。
- 不新增数据库、Redis、HTTP 路由、前端界面、Conversation 状态或任务状态。
- P2.4 至 P2.6 只能消费确认结果；结构化 Agent Call、策略校验和实际分发仍由后续 change 实现。
