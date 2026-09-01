## Context

Interaction Gateway 目前把候选识别的所有非 `matched` 结果直接返回给浏览器。真实多轮测试中，纯追问被识别为 `unrecognized`，因此未进入已经具备历史读取、流式输出和持久化能力的 Conversation Runtime。`chat.general` 是目录中唯一无需确认的通用文本能力，但不能让这一兜底路径绕过目录校验或业务能力的澄清分支。

## Goals / Non-Goals

**Goals:**

- 让非空的普通对话追问在识别为 `unrecognized` 时继续作为 `chat.general` 进入既有流式 Conversation Runtime。
- 复用 Gateway 的服务端目录、确认策略、输入契约和固定分发校验，保持浏览器无权决定执行分支。
- 保持已匹配业务能力、缺失资料、权限不足、候选索引或目录不可用时的受控结果。

**Non-Goals:**

- 不修改候选向量索引、意图模型提示、能力目录结构或确认策略。
- 不把 `needs_clarification`、`pending`、`rejected` 或 `failed` 降级为通用 Chat。
- 不新增 HTTP 接口、数据库迁移或前端特殊协议。

## Decisions

### 在 Gateway 的 `unrecognized` 分支创建受控通用 Chat 评估

Gateway 已拥有原始用户文本、可信主体、目录确认和无确认执行校验。仅当结构化识别返回 `unrecognized` 时，Gateway 用原始、去空白后的文本构造固定 `chat.general` 评估，并复用既有 `_prepare_unconfirmed_execution`。

该校验再次从服务端目录读取能力，要求当前主体可用、策略为 `never`、输入 Schema 允许 `message`，并将固定代码与分发键交给既有 Interaction Chat Stream。浏览器、结构化模型和候选召回都不能指定能力代码或分发键。

备选方案是在候选召回层永久加入 `chat.general`，或改写意图模型提示。前者不能保证模型选择通用 Chat，后者仍依赖模型输出；两者都不能对 `unrecognized` 提供确定行为。Gateway 兜底更小、更确定，并复用现有授权边界。

### 保留非 `unrecognized` 的原始结果

`needs_clarification` 表示已识别到能力但输入不完整，必须继续要求用户补充；`pending`、`rejected`、`failed` 也必须保留原有确认或失败语义。候选索引和目录不可用当前映射为 `needs_clarification`，同样不触发兜底。

### 原样保存用户追问

兜底评估把原始用户文本作为 `message` 输入，而不重新表述或截断。这保证 Conversation Runtime 写入的 user Message、模型当前问题和前端历史一致。

## Risks / Trade-offs

- [候选模型错误地将业务意图标为 `unrecognized`] → 只会得到无副作用的通用文本回答，不会触发 Agent、知识能力或业务执行；明确命中的业务能力和澄清分支不变。
- [目录策略被错误配置为 `never`] → 兜底仍通过固定 `chat.general` 代码、目录能力类型和后续专用流式分支校验，不可借此执行其它能力。
- [通用 Chat 目录项不可用] → 不授权兜底，向浏览器保持原受控 `result` 或目录错误结果。

## Migration Plan

无需数据迁移或 HTTP 契约迁移。部署后新的自然追问会获得流式与持久化行为；回滚只需移除 Gateway 的兜底分支，既有业务能力路由不受影响。

## Open Questions

无。
