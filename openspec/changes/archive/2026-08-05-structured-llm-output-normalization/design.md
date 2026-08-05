## Context

当前 `StructuredLlmPort` 已经为 Tender Application 提供稳定的结构化结果契约，但 GLM 适配器在收到 Provider 响应后直接执行 Pydantic 校验。真实 `glm-5` 已返回了可识别的结构化内容，却使用了 `tender_analysis`、`tender_chunk_analysis` 等外层包装；其他模型还可能把思考内容放入独立字段、标签块或普通文本中。直接校验会把这些 Provider 表达差异错误地当成上游失败。

本 Change 只增加基础设施层的原始响应归一化和扩展插口。Tender Application、Tender Domain、HTTP、MCP 和现有 `StructuredLlmPort` 对外契约保持不变。当前 GLM 和 DeepSeek 都使用 OpenAI-compatible JSON Object 请求，因此相同的 Schema 包装规则应由通用归一化器处理。

## Goals / Non-Goals

**Goals:**

- 在 Provider 原始响应和目标 Pydantic Schema 之间建立可扩展的归一化装饰层。
- 兼容当前 GLM 和 DeepSeek 的直接 JSON、已知 Schema 包装 JSON、代码块和可分离的思考字段。
- 通过 Provider/模型归一化器接口，为未来 `A: ...` 等非 JSON 输出格式预留独立实现位置。
- 归一化成功后继续返回现有 `StructuredLlmResult`，让 Tender Application 无感使用。
- 对不确定、无法安全转换或字段类型不匹配的结果稳定失败，并保留脱敏诊断信息。

**Non-Goals:**

- 不实现没有确定解析规则的 Provider 专属自然语言格式。
- 不修改 Tender Application、分块算法、归并规则、HTTP/MCP 契约或 DOCX Renderer。
- 不调用第二次 LLM 修复 JSON，不根据行业常识补字段，不把任意思考文本强行转换为业务结果。
- 不保存或展示模型思考原文，不把归一化层扩展为 Conversation 或 Agent Runtime。

## Decisions

### 1. 保持业务端口不变，在原始响应层增加装饰器

Tender Application 继续依赖 `StructuredLlmPort.invoke(request, output_schema)`。Infrastructure 内部增加原始 Provider 响应契约和归一化装饰器：装饰器调用 Provider Raw Adapter，交给对应的 `ProviderOutputNormalizer`，再执行统一 Schema 校验并组装 `StructuredLlmResult`。

不把归一化器包在当前已经返回 typed result 的 GLM Adapter 外面，因为当前 Adapter 会在归一化之前抛出异常，外层无法获得原始响应。

```text
TenderApplication
    -> StructuredLlmPort（现有契约）
        -> StructuredOutputDecorator
            -> ProviderOutputNormalizer
                -> Provider Raw Adapter
                    -> OpenAI-compatible Client
```

### 2. 用归一化器接口隔离 Provider 差异

定义一个接收原始响应、目标 Schema 和 Provider 上下文的归一化接口。GLM 和 DeepSeek 共用 Schema 感知 JSON 归一化器；只有 Provider 存在确定且独有的原始格式时，才通过注册表增加独立实现，而不改 Application 和 Tender Port。

装饰器负责公共流程和失败映射，归一化器只负责对应 Provider 的格式转换。通过 Composition Root 或注册表选择归一化器，不在 Tender 业务代码中写模型名称分支。

### 3. 只做确定性的格式转换

归一化顺序为：提取响应内容 -> 隔离已知思考字段 -> 去除明确的 Markdown JSON 代码块 -> 解析 JSON object -> 解包有限且已知的包装键 -> 用目标 Schema 严格校验。包装键只允许与目标 Schema 和 Provider 配置匹配的已知键，并限制递归层数。

字段类型不一致、多个候选对象无法区分或普通文本无法按 Provider 规则解析时，系统返回结构化失败。不得把对象序列化成字符串、删除无法识别字段或使用另一次 LLM 进行“修复”。

### 4. 思考内容与业务内容分离

Provider 返回的 `reasoning_content` 等独立思考字段只用于内部耗时/长度统计，不进入业务 JSON。只有明确的 `<think>...</think>` 标签才允许按 Provider 规则从内容中分离；无法确认边界时不猜测，直接按不兼容格式失败。日志和 HTTP/MCP 响应不包含思考原文。

### 5. 保持错误和可观测性边界

归一化错误继续映射为现有 `UpstreamServiceError` 或 Tender 的稳定业务错误。日志记录 Provider、模型、Prompt 版本、Schema、响应格式分类、耗时和异常类型，不记录原始招标文本、用户关注点、思考原文、API Key 或完整响应。

### 6. 用替身和真实 GLM 分层验证

单元测试覆盖直接 JSON、GLM/DeepSeek 共用的 Schema 包装 JSON、代码块、思考字段、无效 JSON、字段类型错误和未知包装。集成验证分别覆盖现有 Provider 适配器，真实 GLM/DeepSeek 可确认归一化后的结果通过 Tender Schema 校验并继续到真实 DOCX Renderer；真实语义仍需人工检查，不把 Provider 响应成功等同于业务语义正确。

## Risks / Trade-offs

- [风险] 不同模型的非 JSON 格式差异无法由通用逻辑覆盖。→ 由独立 Provider Normalizer 扩展；未实现的格式稳定失败，不静默猜测。
- [风险] 过度宽松的解包或字段转换会掩盖模型错误。→ 只允许有限已知包装和严格 Schema 校验，禁止通用“修复”。
- [风险] 思考字段命名和位置不统一。→ Provider Normalizer 负责识别，公共层只处理已声明的标准字段；无法确认时丢弃业务转换并失败。
- [风险] 增加一次解析层可能扩大调试范围。→ 保持 `StructuredLlmPort` 不变，使用 Fake Raw Adapter 和固定响应夹具覆盖装配与错误映射。

## Migration Plan

无数据库迁移、HTTP 契约迁移或持久化迁移。先将现有 GLM Adapter 拆分为原始响应调用和归一化装配，再由 Composition Root 返回归一化后的 `StructuredLlmPort`。失败时可回滚到现有 GLM Adapter，但不能把未经归一化和真实 Tender 验收的结果标记为完成。

## Open Questions

- 当前 GLM 的已知包装键是否只允许按目标 Schema 名称自动推导，还是在 Provider 配置中显式登记；初版可同时支持显式映射和严格的 Schema 名称映射。
- DeepSeek 后续如果返回普通 `A: ...` 文本，具体标签到字段的映射应由其独立 Normalizer 和对应 Prompt 共同定义，不在本 Change 中提前固化。
