## Context

当前能力目录的 Tender 输入要求 `file_name` 和 `content_base64`，这适合旧同步入口但不适合复用。解析层应在 Gateway 与具体 Agent Adapter 之间工作，将引用解析为内部值。

## Goals / Non-Goals

**Goals:**

- 让能力以声明方式限制附件类型、数量和大小。
- 在执行前读取并校验真实附件，避免客户端伪造路径或内容。

**Non-Goals:**

- 不实现文件上传和存储。
- 不直接修改 Tender Application 的业务逻辑。

## Decisions

- 附件字段使用不透明 ID；解析器通过 Attachment Access Port 获取内容。
- 解析结果只在服务端传递给后续 Adapter，不返回完整内容到 LLM、确认卡或会话事件。
- 解析失败统一为输入澄清/拒绝，不创建可执行提议。

## Attachment Field Declaration

能力在 `input_schema.properties.<field>.x-attachment` 声明附件约束：

- `allowed_media_types`：非空、无重复的允许媒体类型列表。
- `max_size_bytes`：每个附件的正整数大小上限。
- `max_count`：正整数数量上限；为 `1` 时字段为 `string`，大于 `1` 时字段为 `array`，且 `items.type` 为 `string`。

客户端只能为这些字段提交不透明附件 ID。解析器以可信主体和可选会话构造访问上下文，读取后以服务端内部 `ResolvedAttachment` 值替换 ID；该值不会由 HTTP 响应、确认卡或会话事件序列化。

## Risks / Trade-offs

- [能力声明不足] -> 缺少安全限制时拒绝解析，而不是默认放开所有类型。
- [重复读取成本] -> 解析器可返回请求级不可变结果，生命周期仍由附件存储控制。

## Migration Plan

先支持附件字段的新增能力；旧的 Base64 输入保持兼容，待 Tender Adapter 完成后再切换。

## Open Questions

是否允许附件数组以及每个元素的角色命名由具体能力 Spec 决定。
