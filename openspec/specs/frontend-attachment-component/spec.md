# Frontend Attachment Component Specification

## Purpose

提供可复用的前端附件选择、上传、进度和失败恢复交互，并且只向业务层暴露服务端返回的动态附件引用，避免组件绑定具体业务能力。

## Requirements

### Requirement: 通用附件交互

前端 MUST 提供可复用的附件选择、上传、进度、失败、重试和移除状态，并向业务层输出服务端返回的动态附件引用。

#### Scenario: 选择并上传

- **WHEN** 用户选择合法文件并提交上传
- **THEN** 组件显示上传状态和进度
- **AND** 成功后输出动态附件引用

#### Scenario: 上传失败重试

- **WHEN** 上传因网络或服务端校验失败
- **THEN** 组件显示可理解的错误状态
- **AND** 用户可以重新上传，不污染聊天文本

#### Scenario: 纯文本聊天回归

- **WHEN** 用户不选择附件发送纯文本
- **THEN** 现有聊天流程保持不变
