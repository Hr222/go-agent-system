## Context

当前 `Settings` 仅有一套 `ZHIPU_*` 端点、模型、超时和输出上限。仓库现有配置已连通 Coding Plan，但当前要优先消耗有有效期的 GLM-4.5-Air 资源包。若通过手改同一套环境变量在两个来源间切换，真实流量、测试结果和资源消耗无法稳定归因。

`modules/llm` 的 Port 已经是 Provider-neutral，`infrastructure/llm` 负责 OpenAI-compatible SDK 与 Provider 配置，Composition Root 负责组装。因此 Profile 选择属于 Settings、Infrastructure 和 Composition Root，不进入 Application、Domain、HTTP 或前端。

## Goals / Non-Goals

**Goals:**

- 将 GLM 文本调用拆成互不覆盖的 `resource` 与 `coding_plan` Profile。
- 默认选用资源包：标准 `https://open.bigmodel.cn/api/paas/v4` 和 `glm-4.5-air`。
- 让 Coding Plan 保持可选：`https://open.bigmodel.cn/api/coding/paas/v4` 及其独立模型、超时和输出预算。
- 让同一 Client Factory 暴露所选 Profile 的脱敏标识，便于测试和日志确认当前实际来源。
- 保持一个 GLM API Key 配置入口；两个 Profile 共享该 Key，但不共享可变端点、模型或预算配置。

**Non-Goals:**

- 不改变 GLM 的 thinking、首包判断、SDK 重试、流式超时、限流或熔断；这些由后续子 change 处理。
- 不自动根据失败、余额或到期日切换 Profile；切换必须由服务端配置完成。
- 不接入 GLM-4.1V-Flash 视觉资源包，也不修改纯文本 LLM Port。
- 不修改 HTTP 契约、数据库、Conversation 状态、前端选择器或 API Key 存储方式。

## Decisions

### 以 GLM Profile 选择补充既有 Provider 选择

保留 `LLM_PROVIDER=glm|deepseek`，并新增 `GLM_RUNTIME_PROFILE=resource|coding_plan`，仅在 Provider 为 `glm` 时生效。`LlmProviderConfig` 增加可选的 Profile 标识，Client Factory 用其创建和记录实际配置。

这避免把资源来源伪装为新的 Provider，也让现有 GLM Adapter、结构化归一化器和 Composition Root 分支保持不变。替代方案是增加 `glm_resource`、`glm_coding` 两个 Provider；这会使每个 Provider 分支、测试和后续 Provider-neutral 逻辑膨胀，因此不采用。

### 为两个 Profile 使用独立命名空间

新增 `ZHIPU_RESOURCE_*` 与 `ZHIPU_CODING_*` 配置组：端点、模型、超时、温度和最大输出均各自独立；API Key 继续使用 `ZHIPU_API_KEY`。资源包的默认端点和模型固定为标准 PaaS 与 `glm-4.5-air`，Coding Plan 的默认端点固定为 `api/coding/paas/v4`。

为避免已部署环境升级后立即失效，未设置新 Profile 配置时保留对旧 `ZHIPU_BASE_URL`、`ZHIPU_CHAT_MODEL`、`ZHIPU_TIMEOUT_SECONDS`、`ZHIPU_TEMPERATURE`、`ZHIPU_MAX_TOKENS` 的资源包 Profile 回退读取。`.env.example` 和本地 `.env` 迁移为新变量；新变量存在时它们优先。

### 验证以配置构造和受控冒烟为边界

自动化测试验证两个 Profile 的隔离、默认值、旧配置回退、Composition Root 组装和日志脱敏。另提供不自动执行的 Profile 冒烟命令/脚本参数，用最小文本调用分别验证资源包和 Coding Plan，不打印 API Key 或提示词。

资源包实际承担流量前，人工在资源包 Profile 上完成一次聊天流式与一次结构化调用；Coding Plan 只完成同等基础连通性验证。本 change 不以真实调用成功替代自动化回归。

## Risks / Trade-offs

- [标准资源包实际模型名或端点与当前页面不一致] → 只将截图确认的 `glm-4.5-air` 写为默认值，真实验证失败时保留配置覆盖点并向用户报告，不在代码中猜测替代模型。
- [旧部署只有 `ZHIPU_*` 配置] → 资源包 Profile 支持旧变量回退，同时文档明确新变量优先级和迁移方式。
- [两个 Profile 共用 API Key，但账户权限不同] → 连接失败映射为既有安全配置/上游错误，不记录 Key；人工冒烟确认账户权限。
- [误以为 Profile 分离已经解决超时] → 本 Change 明确排除超时行为，后续 `stabilize-glm-fast-streaming` 才解决 thinking 和流式 activity 语义。

## Migration Plan

1. 部署前将现有 GLM 参数拆分为 `ZHIPU_RESOURCE_*` 与 `ZHIPU_CODING_*`，并设定 `GLM_RUNTIME_PROFILE=resource`。
2. 以资源包 Profile 执行受控聊天流式和结构化冒烟；以 Coding Plan Profile 执行同一基础冒烟，但不切换主流量。
3. 若资源包验证失败，将 `GLM_RUNTIME_PROFILE` 切回 `coding_plan`；无需数据库迁移或代码回滚。
4. 资源包余额耗尽或到期后，人工修改 `GLM_RUNTIME_PROFILE=coding_plan` 并复跑冒烟验证。

## Open Questions

- 无阻塞问题。资源包和 Coding Plan 是否使用相同 API Key 将由本地配置与受控冒烟验证；设计本身允许同一 Key。
