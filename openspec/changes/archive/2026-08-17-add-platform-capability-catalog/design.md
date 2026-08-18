## Context

架构已将 `Platform Capability Catalog` 定义为统一交互入口的目录，但当前能力发现偏向 Agent Runtime。平台还需要用一张持久化目录表统一描述 Chat、知识库问答和政策判断等非 Agent 能力。

## Goals / Non-Goals

**Goals:**

- 在 `modules/interaction` 建立平台级能力目录，并以 `platform_capability` 表作为登记和启停的事实来源。
- 让目录条目完整描述识别、确认和受控分发所需的业务边界。
- 让 Agent Runtime 读取 Agent 条目而非拥有另一份注册表。

**Non-Goals:**

- 不提供目录管理 UI、向量检索或自然语言入口；本 Change 只提供表、Repository 和应用层查询能力。
- 不实现 Dispatcher，不修改现有 HTTP 路由。

## Decisions

### 1. 目录条目采用稳定能力代码和不可执行分发键

条目包含能力代码、业务描述、输入输出 Schema、必填资料、确认策略、启用状态、权限、超时、错误边界和分发键。分发键是代码可验证的标识，不是 URL、类名或可由 LLM 生成的工具名称。

### 2. `platform_capability` 是目录唯一事实来源

新增 `platform_capability` 表保存能力代码、类型、业务描述、输入输出 Schema、必填资料、确认策略、权限、启用状态、超时、错误边界、固定分发键和召回元数据。目录查询通过 Application Port 和 Repository 读取，不允许消费者直接访问 ORM Model。

JSON Schema 与召回元数据使用结构化 JSONB 字段，能力代码建立唯一约束；`capability_type` 区分 Agent 与非 Agent。首版通过迁移或受控种子数据登记现有能力，不新增管理后台。

### 3. 分发键只做受控代码映射

表中保存 `dispatch_key`，但不保存 URL、Python 类名、函数名或任意可执行脚本。Composition Root 将已知分发键映射到固定 Application Use Case；目录加载时校验分发键存在且类型匹配，避免数据库内容成为任意执行入口。

### 4. Runtime 消费目录而不拥有目录

Runtime 仅查询其可处理的 Agent 条目；普通 Chat、RAG 和政策判断仍可登记在同一目录，但不进入 Agent Runtime。这样统一入口能先理解用户目标，再决定是否需要 Agent。

## Risks / Trade-offs

- [目录表数据被错误修改] → 使用数据库约束、应用层校验、审计字段和受控种子/迁移；管理 UI 另行设计权限。
- [目录字段过多导致配置不一致] → 构造时校验必填字段、能力代码唯一性、类型和分发键有效性。
- [旧 Runtime 注册表与目录重复] → 迁移时以目录为唯一来源，补充兼容适配并由测试防止双份定义。

## Migration Plan

先创建 `platform_capability` 表和迁移，写入受控的 Agent 与非 Agent 初始记录，再使 Runtime 从 Repository 查询 Agent 能力。回滚时保留现有 Runtime 直连能力，删除新目录读取路径；禁止新增第二份注册数据。

## Open Questions

首版纳入目录的非 Agent 能力清单在实施时以现有公开用例为准。
