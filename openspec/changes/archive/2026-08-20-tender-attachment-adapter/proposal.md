## Why

Tender Agent 当前能力契约要求 `file_name` 和 `content_base64`，而通用附件链路将提供不透明 `attachment_id`。需要一个业务适配器完成两者之间的转换，同时保持附件存储和其他 Agent 的独立性。

## What Changes

- 为 Tender 声明所需的附件角色和 DOCX 约束。
- 将合法附件引用解析为 Tender Application 所需的内部命令。
- 无附件或非 DOCX 时返回澄清/拒绝，不执行 Tender。

## Capabilities

### New Capabilities

- `tender-attachment-adapter`: 将通用附件映射为 Tender Agent 输入。

### Modified Capabilities

- 无。

## Impact

影响 Tender 能力目录输入映射、Interaction Gateway 与 Tender Adapter；不修改通用附件存储，也不实现其他 Agent。
