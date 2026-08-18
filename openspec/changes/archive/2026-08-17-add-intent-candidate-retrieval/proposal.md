## Why

Structured LLM 不应面对平台全部能力自由选择。先从能力目录召回少量候选，才能降低误选风险并让后续识别结果可解释。

## What Changes

- 基于 Platform Capability Catalog 和通用 Embedding Port 新增能力候选召回用例。
- 为能力描述、同义表达、正反例和检索元数据建立独立的候选索引模型。
- 先提供可测试的内存候选集与相似度排序，不提前引入 pgvector 持久化。
- 明确候选索引不得复用 `kb_policy_chunk`、政策 Repository 或 RAG 检索结果。

## Capabilities

### New Capabilities

- `intent-candidate-retrieval`: 从平台能力目录召回有限、可解释的意图候选。

### Modified Capabilities

- 无。

## Impact

- 依赖 `generic-text-embedding` 和 `platform-capability-catalog` 两个已完成 Change。
- 不改变政策知识库、HTTP 契约、数据库表或 Agent Runtime 的执行行为。
