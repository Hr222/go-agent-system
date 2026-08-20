# security-http-principal-binding Specification

## Purpose
定义 HTTP Security Adapter 如何依据服务端主体模式装配请求主体解析器，并将可信的 `RequestPrincipal` 注入 Interaction 路由，确保客户端提交的权限 Header 不会越权改变服务端决定的主体。
## Requirements
### Requirement: HTTP 主体解析器按模式装配

HTTP Security Adapter MUST 按服务端主体模式装配 Resolver，并将解析出的 `RequestPrincipal` 注入 Interaction 路由。

#### Scenario: anonymous 模式
- **WHEN** 服务端主体模式为 anonymous
- **THEN** HTTP 请求获得匿名主体

#### Scenario: static 模式
- **WHEN** 服务端主体模式为 static 且配置合法
- **THEN** HTTP 请求获得配置的静态主体和权限

#### Scenario: 客户端 Header 不改变主体
- **WHEN** HTTP 请求携带伪造权限 Header
- **THEN** 注入主体仍由服务端模式决定
