# Tender Attachment Adapter Specification

## Purpose

将受控附件引用安全适配为 Tender Agent 的服务端输入，校验主体、格式和大小约束，同时维持现有能力目录、权限过滤和显式确认边界。

## Requirements

### Requirement: Tender 附件输入适配

系统 MUST 将当前主体可访问且满足 DOCX 约束的附件引用转换为 Tender Agent 可消费的服务端输入，并在执行前继续执行现有能力和确认校验。

#### Scenario: 合法 DOCX 附件

- **WHEN** 用户提交有效 DOCX 附件引用并请求生成投标骨架
- **THEN** 系统生成 Tender 输入并进入既有确认流程
- **AND** 不向客户端或 LLM 暴露完整 Base64 内容

#### Scenario: 非 DOCX 附件

- **WHEN** 用户提交图片、PDF 或其他非 DOCX 附件给 Tender
- **THEN** 系统返回明确的输入澄清或拒绝
- **AND** 不调用 Tender Application

#### Scenario: 附件不可访问

- **WHEN** 附件过期、已消费或不属于当前主体
- **THEN** 系统返回受控输入错误
- **AND** 不执行 Tender Agent
