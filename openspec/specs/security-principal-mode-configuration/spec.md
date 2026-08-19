# security-principal-mode-configuration Specification

## Purpose
TBD - created by archiving change security-principal-mode-configuration. Update Purpose after archive.
## Requirements
### Requirement: 主体模式显式配置

系统 MUST 支持 `anonymous` 和 `static` 两种主体模式，默认模式 MUST 为 `anonymous`。

#### Scenario: 缺省配置保持匿名
- **WHEN** 未配置主体模式
- **THEN** 配置解析成功并选择匿名模式

#### Scenario: 非法模式被拒绝
- **WHEN** 主体模式不是 `anonymous` 或 `static`
- **THEN** 配置加载失败并给出稳定的配置错误

### Requirement: 静态主体配置完整性

系统 MUST 在 `static` 模式下要求非空主体标识，并将权限配置解析为去重后的权限集合。

#### Scenario: 静态配置成功
- **WHEN** static 模式包含合法主体和权限文本
- **THEN** 配置提供可构造静态 Resolver 的主体和权限

#### Scenario: 静态主体缺失
- **WHEN** static 模式的主体标识为空
- **THEN** 配置加载失败

