## Purpose

定义 GLM 资源包与 Coding Plan 的服务端运行 Profile 选择、隔离配置和受控验证行为。

## Requirements

### Requirement: GLM 运行 Profile 独立选择

系统 MUST 在 `LLM_PROVIDER=glm` 时通过服务端 `GLM_RUNTIME_PROFILE` 选择 `resource` 或 `coding_plan` Profile；该选择不得由 HTTP 请求、前端参数、Conversation 数据或模型输出控制。未配置选择时系统 MUST 使用 `resource`。

#### Scenario: 默认使用资源包 Profile

- **WHEN** 服务端选择 GLM Provider 且未配置 `GLM_RUNTIME_PROFILE`
- **THEN** 系统使用资源包 Profile 组装 GLM Client
- **AND** 不访问 Coding Plan 的端点、模型或预算配置

#### Scenario: 显式使用 Coding Plan Profile

- **WHEN** 服务端配置 `LLM_PROVIDER=glm` 且 `GLM_RUNTIME_PROFILE=coding_plan`
- **THEN** 系统使用 Coding Plan Profile 组装 GLM Client
- **AND** 既有 Chat 和 Structured LLM Port 对调用方保持不变

#### Scenario: 非 GLM Provider 不受 Profile 影响

- **WHEN** 服务端配置 `LLM_PROVIDER=deepseek`
- **THEN** 系统继续使用 DeepSeek 配置组装 Client
- **AND** 不读取或要求 GLM Profile 配置

### Requirement: 资源包与 Coding Plan 配置隔离

系统 MUST 为资源包和 Coding Plan 分别保存端点、模型、超时、温度和最大输出配置。资源包默认使用标准 PaaS 端点与 `glm-4.5-air`，Coding Plan 默认使用 `api/coding/paas/v4`。修改一个 Profile 的配置不得改变另一个 Profile 的有效配置。

#### Scenario: 资源包配置覆盖默认值

- **WHEN** 服务端为资源包 Profile 配置自定义端点、模型或预算
- **THEN** 资源包 Client 使用这些配置
- **AND** Coding Plan Client 仍使用其独立配置或默认值

#### Scenario: 旧 GLM 配置迁移兼容

- **WHEN** 服务端未设置新的资源包配置但仍设置旧 `ZHIPU_*` 端点、模型或预算变量
- **THEN** 资源包 Profile 使用这些旧变量构造 Client
- **AND** 新资源包变量存在时优先使用新变量

### Requirement: Profile 可验证且不泄露敏感数据

系统 MUST 能在测试和脱敏运行日志中识别实际选用的 GLM Profile、端点和模型。系统 MUST NOT 记录 API Key、完整提示词、模型响应或资源包余额。

#### Scenario: 受控验证两个 Profile

- **WHEN** 运维人员分别选择资源包和 Coding Plan Profile 执行基础 GLM 冒烟验证
- **THEN** 每次验证均使用所选 Profile 的端点和模型
- **AND** 验证输出只包含 Profile、端点、模型、耗时和成功或失败分类

#### Scenario: 配置或上游失败

- **WHEN** 所选 Profile 缺少 API Key 或 Provider 调用失败
- **THEN** 系统返回既有的安全配置或上游失败语义
- **AND** 错误与日志不包含 API Key、完整提示词或完整 Provider 响应
