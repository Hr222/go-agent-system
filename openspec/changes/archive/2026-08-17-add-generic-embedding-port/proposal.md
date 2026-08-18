## Why

现有 Embedding 适配器能够生成查询向量，但批量接口与 Ingestion 的 `ChunkItem` 绑定。意图识别、知识库和入库流程都需要向量能力，却不应互相依赖领域对象。

## What Changes

- 在 `modules/llm` 定义通用纯文本 Embedding Port，支持单条和批量文本输入。
- 让现有 Provider 适配器实现该 Port，并保留入库流程的领域转换在 Ingestion 内部。
- 用契约测试固定输入、维度、顺序、空输入和 Provider 失败边界。
- 不新增意图目录、向量索引、HTTP 接口或数据库表。

## Capabilities

### New Capabilities

- `generic-text-embedding`: 为应用模块提供不泄露领域对象的纯文本向量生成契约。

### Modified Capabilities

- 无。

## Impact

- 影响 `app/modules/llm`、`app/infrastructure/llm` 和 Ingestion 对 Embedding 的调用方式。
- 不改变现有 HTTP 契约、Embedding Provider、数据库模式或政策知识检索结果。
