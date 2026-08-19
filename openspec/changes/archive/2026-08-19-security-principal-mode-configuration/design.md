## Context

应用配置集中在 `app/shared/config.py`。静态主体是过渡适配器，需要通过显式环境变量启用，而不能根据开发环境猜测。

## Goals / Non-Goals

**Goals:**

- 以配置表达主体模式、主体标识和权限集合。
- 在应用启动时发现非法配置。

**Non-Goals:**

- 不实现认证协议或用户模块。
- 不接受客户端 Header 覆盖配置。

## Decisions

- 使用枚举值 `anonymous`/`static`，默认 `anonymous`。
- 静态模式要求非空主体；权限按逗号分隔并去空白，空权限可以显式表达无权限主体。
- 配置校验放在 Pydantic Settings 层，避免请求到达后才失败。

## Risks / Trade-offs

- [环境文件残留 static 配置] -> 默认值和启动日志明确显示模式；生产部署必须显式审查配置。
- [权限字符串拼写错误] -> 只做格式级校验，能力是否存在仍由目录授权层决定。

## Migration Plan

新增配置均有安全默认值，无数据迁移；回滚时移除 static 配置即可回到匿名模式。

## Open Questions

正式认证接入后由独立 Change 决定配置来源和优先级。

