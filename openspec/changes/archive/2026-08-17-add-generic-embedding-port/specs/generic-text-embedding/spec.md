## ADDED Requirements

### Requirement: 通用 Port 接受纯文本并生成向量
系统 MUST 通过 LLM 能力层提供单条和批量纯文本 Embedding 契约，调用方无需传入 Ingestion、Knowledge 或 Agent 的领域对象。

#### Scenario: 应用模块为文本生成单条向量
- **WHEN** 调用方向通用 Port 提交一条非空文本
- **THEN** 系统返回该文本对应的向量结果
- **AND** 结果不包含 `ChunkItem`、Repository 或检索领域对象

#### Scenario: 批量向量结果与输入保持对应
- **WHEN** 调用方向通用 Port 提交多条非空文本
- **THEN** 系统按输入顺序返回等数量的向量结果

### Requirement: 空输入和 Provider 失败可观察
系统 MUST 拒绝空白文本，并将 Provider 调用失败映射为 LLM 契约中的明确错误；系统不得返回伪造向量。

#### Scenario: 调用方提交空白文本
- **WHEN** 单条或批量请求包含空白文本
- **THEN** 系统返回可识别的输入校验失败
- **AND** 系统不调用 Embedding Provider

#### Scenario: Provider 调用失败
- **WHEN** Provider 超时、返回无效结果或不可用
- **THEN** 系统返回明确失败
- **AND** 调用方不会收到零向量或部分成功结果
