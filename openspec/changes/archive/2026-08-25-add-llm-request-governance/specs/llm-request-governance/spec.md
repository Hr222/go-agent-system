## ADDED Requirements

### Requirement: OpenAI-compatible LLM 请求共享受控配额

系统 MUST 对同一有效 OpenAI-compatible Provider 配置创建的 Chat、流式 Chat、结构化调用和 RAG 调用共享请求治理状态。每次即将发起的真实 Provider 尝试 MUST 消耗一枚令牌，并在一段时间内持有一个并发名额；限额不得由 HTTP 请求、前端状态、Conversation 数据或模型输出指定。

#### Scenario: 不同调用形态共享同一 Provider 配额

- **WHEN** 服务端在同一有效 Provider 配置下先后发起普通 Chat、结构化调用和 RAG 调用
- **THEN** 每一次实际 Provider 尝试均计入同一个速率限制和并发上限
- **AND** 调用方无需也不能传入配额参数

#### Scenario: 重试产生新的上游尝试

- **WHEN** 一次可重试的 Provider 调用失败并由既有重试策略再次尝试
- **THEN** 每一次尝试都必须重新经过请求治理
- **AND** 不可重试错误仍按既有安全错误语义立即失败

### Requirement: 请求速率限制以令牌桶执行

系统 MUST 以服务端配置的每分钟请求数和突发量维护令牌桶。没有可用令牌时，系统 MUST 在调用 Provider 前等待令牌；等待中的取消不得发起上游请求，也不得使用忙轮询。

#### Scenario: 超过短时突发量

- **WHEN** 同一 Provider 配置在短时间内耗尽其突发令牌
- **THEN** 后续调用在服务端等待令牌补充后才发起 Provider 请求
- **AND** 不因为本地突发而向 Provider 主动返回或制造 `429`

#### Scenario: 配额等待期间取消流式调用

- **WHEN** 流式调用在等待令牌或并发名额时被消费者取消
- **THEN** 系统不创建上游流
- **AND** 已等待的调用不会永久占用并发名额

### Requirement: 并发名额覆盖完整的上游流生命周期

系统 MUST 以服务端配置限制同时在途的 Provider 请求数。流式调用从创建上游流开始到流关闭、完成、失败或取消时持有名额；同步调用在 Provider 函数返回或抛出时释放名额。

#### Scenario: 流式调用正常结束

- **WHEN** 已取得并发名额的 Provider 流正常完成
- **THEN** 系统关闭或耗尽该流并释放名额
- **AND** 后续等待中的调用可以继续进入 Provider

#### Scenario: 首个上游活动前重试流式调用

- **WHEN** 流式尝试在首个上游活动前失败且既有重试策略允许重试
- **THEN** 系统关闭旧流并释放其名额
- **AND** 下一次尝试重新经过令牌桶和并发控制

#### Scenario: 旧 HTTP 流式特例不再控制上游并发

- **WHEN** 浏览器调用既有流式交互入口
- **THEN** 系统使用有效 Provider 的请求治理配置控制上游并发
- **AND** 不再使用只覆盖该 HTTP 入口的独立并发限制

### Requirement: 请求治理配置和日志安全可调

系统 MUST 校验请求速率、突发量和并发上限均为有效正值，且突发量不得大于每分钟请求数。系统 MUST 记录可用于排查排队的脱敏治理事件，但 MUST NOT 在治理日志中记录 API Key、提示词、模型响应、资源包余额或原始 Provider 响应。

#### Scenario: 运行时配置无效

- **WHEN** 服务端将请求速率、突发量或并发上限配置为无效值
- **THEN** 应用配置加载失败并指出无效配置项
- **AND** 不启动一个使用未定义配额的 Provider Client

#### Scenario: 记录治理等待

- **WHEN** 调用因令牌或并发限制而等待
- **THEN** 日志只包含 Provider、Profile、受限阶段和等待时长等运行元数据
- **AND** 日志不包含敏感凭据或用户和模型文本
