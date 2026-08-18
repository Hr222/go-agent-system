## Context

当前 `GiteeEmbeddingClient` 已支持查询向量，但批量方法接收 Ingestion 的 `ChunkItem`。这使其他应用模块无法只通过 LLM 能力层获取向量，也让 Ingestion 的领域对象泄漏到基础设施适配器。

## Goals / Non-Goals

**Goals:**

- 在 LLM 能力层提供与领域对象无关的纯文本 Embedding 契约。
- 让当前 Provider 适配器复用现有模型配置，支持单条和批量调用。
- 将 Ingestion 的 `ChunkItem` 到文本、向量回填的转换留在 Ingestion 内。

**Non-Goals:**

- 不更换模型、Provider、向量维度或向量数据库。
- 不创建意图索引、能力目录或 HTTP 接口。

## Decisions

### 1. Port 只接受文本并保持批量顺序

定义单条和批量纯文本方法；批量结果与输入一一对应并保留顺序。这样调用方可以将自己的实体映射为文本，而无需共享 `ChunkItem`、知识库切块或其他领域类型。

### 2. 由 LLM Adapter 处理 Provider 调用，由应用模块处理领域映射

`infrastructure/llm` 负责请求、超时和错误映射；Ingestion 继续负责切块、持久化和向量回填。该划分让后续 Interaction 可直接依赖 LLM Port，而不是跨模块调用 Ingestion。

### 3. 空文本和 Provider 异常显式失败

Port 不对空白文本静默生成结果；调用失败返回既有 LLM 错误契约。调用方不得将失败伪装成零向量或空候选，以免后续召回产生难以诊断的错误。

## Risks / Trade-offs

- [调整 Ingestion 调用路径导致入库回归] → 用现有入库向量化场景覆盖适配后的调用。
- [Provider 批量能力与 Port 约束不一致] → 在 Adapter 中拆批，并验证结果数量、顺序和向量维度。
- [通用 Port 被误解为知识库查询能力] → 契约只表达文本到向量，不暴露检索、Repository 或切块对象。

## Migration Plan

先增加通用 Port 与 Adapter 测试，再将 Ingestion 的向量生成改为先提取文本后调用 Port。没有数据迁移；出现回归时可将 Ingestion 调用回退到原适配器路径。

## Open Questions

无。
