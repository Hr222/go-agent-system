## Context

附件上传发生在 HTTP 边界，消费可能发生在确认后的另一请求。当前主体已有稳定 `subject`，Proposal Store 也按主体绑定；附件应采用同样的可信主体边界。

## Goals / Non-Goals

**Goals:**

- 防止跨主体和跨会话读取附件。
- 支持 TTL、显式丢弃和一次性消费策略。

**Non-Goals:**

- 不实现登录、用户表或完整 ACL。
- 不决定具体 Agent 的附件字段。

## Decisions

- 元数据保存 `subject` 和可选 `conversation_id`，读取时同时校验。
- 使用服务端状态记录 consumed/expired，客户端只持有不透明 ID。
- 测试使用两个静态主体和真实临时文件，不用固定路径替代访问控制。

## Risks / Trade-offs

- [匿名主体无法隔离] -> 附件消费能力要求静态或真实主体；匿名上传默认不可跨请求消费。
- [一次性消费影响重试] -> 由能力适配器明确选择可重复读取或消费模式。

## Migration Plan

先对通用附件启用绑定；现有政策流水线继续使用自己的上传状态，待独立迁移 Change 决定是否统一。

## Open Questions

会话绑定的持久化介质可先使用短 TTL 进程存储，生产部署再评估共享存储。

