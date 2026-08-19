## Why

静态主体实现需要明确的服务端启用方式，否则测试替身容易被隐式带入运行环境。配置应同时保留当前匿名默认值，并拒绝不完整或不受支持的模式。

## What Changes

- 增加 `anonymous` 和 `static` 两种主体模式配置。
- 增加静态主体标识和权限集合配置。
- 对模式、主体和权限进行启动期校验。

## Capabilities

### New Capabilities

- `security-principal-mode-configuration`: 受控选择 HTTP 主体解析模式。

### Modified Capabilities

- 无。

## Impact

影响 `Settings` 和配置测试；不直接改变 Resolver 绑定，不修改数据库或 HTTP 响应契约。默认模式必须继续为匿名。

