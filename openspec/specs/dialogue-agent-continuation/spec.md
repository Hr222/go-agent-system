## Purpose

定义已完成单 Agent 调用如何在同一 Conversation 中安全续写为最终 assistant Message。

## Requirements

### Requirement: 已完成的 Agent 结果可以生成同一轮 assistant Message

系统 MUST 允许 Dialogue 应用服务根据指定 Conversation 中已持久化的 `agent_result` 生成一次自然语言 assistant Message。续写只能由已完成的 Agent 调用触发，不得重新经过意图识别或重新调用 Agent Runtime。

#### Scenario: Tender Agent 成功后生成最终回答

- **WHEN** 指定 Conversation 存在唯一的已完成 `agent_result`，且关联 `call_id` 与 Conversation 一致
- **THEN** 系统使用现有 Conversation 历史和安全结果投影调用 Chat LLM
- **AND** 将非空模型回答持久化为该 Conversation 的 assistant Message
- **AND** 返回回答、模型元数据、Prompt 版本和 Token 使用信息

#### Scenario: Agent 结果不存在时不调用模型

- **WHEN** 指定 Conversation 中找不到关联 `agent_result`
- **THEN** 系统返回稳定的 `AGENT_RESULT_UNAVAILABLE` 错误
- **AND** 不调用 Chat LLM
- **AND** 不写入 assistant Message

### Requirement: 续写上下文必须保留历史顺序并隔离结果数据

系统 MUST 通过现有 Context Builder 选择 Conversation 的有序消息后缀，并把 `AgentResultProjector` 产生的安全 JSON 作为本次续写数据。系统 MUST NOT 将原始文件字节、Provider 响应、权限集合、异常堆栈或未经投影的执行器对象传入模型或持久化消息。

#### Scenario: 历史消息和 Agent 结果共同进入模型

- **WHEN** Conversation 已有按顺序排列的用户和助手消息，且存在安全的 Agent 结果
- **THEN** Chat LLM 接收到原始角色顺序的历史消息和标记为结果数据的续写指令
- **AND** Agent 结果不会被伪装成新的用户历史消息

#### Scenario: 结果负载包含敏感或二进制字段

- **WHEN** `agent_result` 负载包含 `content_base64`、原始字节、Provider 响应、权限或异常字段
- **THEN** 系统拒绝不安全负载或仅使用已安全投影的字段
- **AND** 这些字段不会出现在 Chat LLM 请求或 assistant Message 中

### Requirement: 续写失败不得伪造 assistant Message 或重复执行 Agent

系统 MUST 将模型不可用、空回答、上下文预算不足和结果序列化失败映射为稳定错误。失败路径 MUST 保留已有 Conversation 消息与 Agent 事件，不写入空 assistant Message，且不得再次调用 Agent Runtime。

#### Scenario: Chat LLM 返回空回答

- **WHEN** Agent 结果有效但 Chat LLM 返回空白内容
- **THEN** 系统返回 `CONTINUATION_EMPTY_RESPONSE`
- **AND** Conversation 不新增 assistant Message
- **AND** Agent Runtime 调用次数保持不变

#### Scenario: Provider 调用失败

- **WHEN** Chat LLM Provider 超时或返回受控失败
- **THEN** 系统返回 `CONTINUATION_LLM_UNAVAILABLE`
- **AND** 已有 `agent_result` 事件保持不变
- **AND** 系统不重新执行 Agent

### Requirement: 现有 Chat 确认响应可以携带最终回答和结构化结果

系统 MUST 在确认后的 Agent 执行成功且续写成功时，沿用现有 Interaction Gateway Response 外形返回 `answer`、安全的 `agent_result` 和 Conversation ID。续写失败时仍 MUST 保留安全的结构化 Agent 结果摘要，并返回稳定的续写错误信息。

#### Scenario: 页面获得自然语言回答和 Tender 文件摘要

- **WHEN** 用户确认 Tender Agent 提议，Agent 执行成功且续写成功
- **THEN** HTTP 响应状态为 `completed`
- **AND** `execution_result.answer` 包含最终 assistant Message
- **AND** `execution_result.agent_result` 仅包含安全的结果摘要和文件元数据

#### Scenario: Agent 成功但续写失败

- **WHEN** Agent 已完成而续写失败
- **THEN** HTTP 响应不触发第二次 Agent 执行
- **AND** 响应仍包含安全的 `agent_result`
- **AND** 响应包含稳定的续写错误码和可理解的失败消息
