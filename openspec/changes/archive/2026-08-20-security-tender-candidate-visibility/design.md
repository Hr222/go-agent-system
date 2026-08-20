## Context

候选检索和意图识别在执行前按 `RequestPrincipal.permission_tuple()` 过滤目录。Tender 能力要求 `agent:tender:execute`，而 `chat.general` 不要求权限。该 Change 只证明权限主体改变候选范围。

## Goals / Non-Goals

**Goals:**

- 静态授权主体能进入 Tender 候选识别链路。
- 缺少 `file_name`/文件内容时返回澄清，避免伪造执行输入。

**Non-Goals:**

- 不实现文件上传或真实 Tender LLM 调用。
- 不修改权限目录数据。

## Decisions

- 使用 Fake Catalog、Embedding 和 Structured LLM 验证权限边界，避免测试依赖外部 Provider。
- 通过 HTTP TestClient 覆盖 Resolver，验证真实路由依赖链。
- 将候选识别、确认卡和未执行状态作为可观察结果。

## Risks / Trade-offs

- [真实向量模型排序差异] -> 集成测试固定检索替身，另保留现有目录过滤单测。
- [无文件时误执行] -> 明确断言输入校验返回 clarification 且 handler 调用数为零。

## Migration Plan

无运行时迁移；测试只验证已有目录配置在 static 模式下的行为。

## Open Questions

文件上传接入后由附件分支提供完整执行输入。

