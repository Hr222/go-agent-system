## MODIFIED Requirements

### Requirement: 资源包与 Coding Plan 配置隔离

系统 MUST 为资源包和 Coding Plan 分别保存端点、模型、超时、温度、最大输出、thinking 策略、每分钟请求数、突发量和请求并发上限配置。资源包默认使用标准 PaaS 端点、`glm-4.5-air`、`disabled` thinking 及保守的 `30 RPM / burst 3 / concurrency 3` 请求治理配置；Coding Plan 默认使用 `api/coding/paas/v4`、`glm-5.3`、`low` thinking 及独立的保守请求治理配置。修改一个 Profile 的配置不得改变另一个 Profile 的有效配置。

#### Scenario: 资源包配置覆盖默认值

- **WHEN** 服务端为资源包 Profile 配置自定义端点、模型或预算
- **THEN** 资源包 Client 使用这些配置
- **AND** Coding Plan Client 仍使用其独立配置或默认值

#### Scenario: 资源包 thinking 独立覆盖

- **WHEN** 服务端为资源包 Profile 配置自定义 thinking 策略
- **THEN** 资源包 Client 使用该策略发送请求
- **AND** Coding Plan Client 仍使用其独立的 thinking 配置或默认值

#### Scenario: Coding Plan thinking 独立覆盖

- **WHEN** 服务端为 Coding Plan Profile 配置自定义 thinking 策略
- **THEN** Coding Plan Client 使用该策略发送请求
- **AND** 资源包 Client 仍使用其独立的 thinking 配置或默认值

#### Scenario: 资源包请求治理独立覆盖

- **WHEN** 服务端为资源包 Profile 配置每分钟请求数、突发量或并发上限
- **THEN** 资源包 Client 使用该 Profile 的请求治理配置
- **AND** Coding Plan Client 仍使用其独立配置或默认值

#### Scenario: Coding Plan 请求治理独立覆盖

- **WHEN** 服务端为 Coding Plan Profile 配置每分钟请求数、突发量或并发上限
- **THEN** Coding Plan Client 使用该 Profile 的请求治理配置
- **AND** 资源包 Client 仍使用其独立配置或默认值

#### Scenario: 旧 GLM 配置迁移兼容

- **WHEN** 服务端未设置新的资源包配置但仍设置旧 `ZHIPU_*` 端点、模型或预算变量
- **THEN** 资源包 Profile 使用这些旧变量构造 Client
- **AND** 新资源包变量存在时优先使用新变量
