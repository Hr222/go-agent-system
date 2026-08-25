## Why

当前 GLM 配置只保存一套端点和模型。Coding Plan 的 `api/coding/paas/v4` 已经接入，但带到期日的 GLM-4.5-Air 资源包需要优先承载当前文本业务；两者混用同一组配置会使切换、验证和配额归因不可靠。

## What Changes

- 为 GLM 增加“资源包”和“Coding Plan”两个独立运行 Profile，分别配置端点、模型、超时和输出上限。
- 资源包 Profile 成为默认的 GLM 文本调用来源，默认使用标准 `api/paas/v4` 与 `glm-4.5-air`。
- 保留 Coding Plan 的 `api/coding/paas/v4` Profile，允许仅通过服务端配置显式切换，并为两套 Profile 提供相同的基础连通性验证入口。
- 保持既有 `glm`、`deepseek` Provider 选择和 LLM Port 不变；不引入自动故障切换、限流、重试策略或多模态请求。

## Capabilities

### New Capabilities

- `glm-runtime-profiles`: 定义资源包与 Coding Plan 的服务端 Profile 选择、默认值和隔离配置行为。

### Modified Capabilities

- 无。

## Impact

- 影响服务端 Settings、OpenAI-compatible Client Factory、Composition Root 配置组装和 `.env.example`；本地 `.env` 将迁移到资源包默认 Profile，但不写入或输出任何密钥。
- 不影响 HTTP 请求/响应、数据库、会话状态、前端或既有 LLM Port。
- 涉及外部 GLM Provider：两套端点、模型和预算必须互相独立，日志只记录非敏感的 Profile 名称、端点和模型。
- 旧 `ZHIPU_*` 配置将在本次保留兼容读取或明确迁移，避免已有部署因升级立即失效。
