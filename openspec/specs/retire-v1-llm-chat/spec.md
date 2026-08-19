## Purpose

定义 V1 无状态 LLM Chat HTTP 入口退场后的统一对话边界，确保所有浏览器请求都经过 V2 Interaction Gateway 的识别、授权、确认与受控流式处理，不再保留绕过对话体系的兼容后门。

## Requirements

### Requirement: V1 LLM Chat HTTP 入口必须退场

系统 MUST 不再注册 `/api/v1/llm/chat` 与 `/api/v1/llm/chat/stream`。系统 MUST NOT 为这些地址提供重定向、兼容开关或绕过 Interaction Gateway 的替代分发。

#### Scenario: 访问旧同步入口

- **WHEN** 客户端向 `/api/v1/llm/chat` 发起请求
- **THEN** 系统返回 `404`

#### Scenario: 访问旧流式入口

- **WHEN** 客户端向 `/api/v1/llm/chat/stream` 发起请求
- **THEN** 系统返回 `404`

### Requirement: V2 Interaction 对话入口保持可用

系统 MUST 保留 `/api/v1/interaction/chat/stream` 作为浏览器对话的统一入口。该入口继续经 Gateway 识别、授权和确认，不得由本 change 改回直接 LLM 调用。

#### Scenario: 路由表保留 V2 对话入口

- **WHEN** 应用创建完成
- **THEN** 路由表包含 `/api/v1/interaction/chat/stream`
- **AND** 路由表不包含 V1 LLM Chat 地址
