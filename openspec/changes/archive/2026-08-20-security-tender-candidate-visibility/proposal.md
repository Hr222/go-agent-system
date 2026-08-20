## Why

当前匿名主体无法通过权限过滤看到 Tender 能力，导致自然语言请求退回通用聊天。需要在已有静态主体模式下验证候选召回、目录复核和确认流程，而不是放开 Tender 的目录权限。

## What Changes

- 增加静态授权主体访问 Tender 能力的 Interaction 集成测试。
- 验证匿名主体和伪造 Header 仍无法发现受保护能力。
- 对缺少 Tender 文件输入的请求验证澄清结果，不执行 Agent。

## Capabilities

### New Capabilities

- `security-tender-candidate-visibility`: 受权限控制的 Tender 候选识别行为。

### Modified Capabilities

- 无。

## Impact

主要影响 Interaction 集成测试和测试替身；不改变 Tender 目录权限、上传接口或 Agent Runtime 实现。

