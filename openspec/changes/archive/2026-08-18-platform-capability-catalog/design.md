## Context

仓库已有 `platform_capability` 持久化表、`PlatformCapability` 领域对象、`CapabilityCatalogPort`、PostgreSQL Repository 和 `PlatformCapabilityCatalog`。目录能够统一描述 Agent、通用对话、知识问答和政策判断能力；读取时过滤禁用条目和无权限条目，Composition Root 还会校验 `dispatch_key` 只能指向固定的受控目标。

V2 已完成 Conversation 与基础 Dialogue Runtime，但尚未把自然语言识别、确认和 Agent 调用接入新的对话轮次。P2.1 是这些后续 change 的共同前置：它确认目录是能力事实来源，而不是把原有 Gateway 或 Dispatcher 提前并入 Dialogue Runtime。

## Goals / Non-Goals

**Goals:**

- 让 V2 后续模块只通过 `CapabilityCatalogPort` 读取可用能力，避免再定义并行的 Agent 或工作流注册来源。
- 保留当前目录的字段和安全约束：稳定能力代码、类型、Schema、必填字段、权限、确认策略、启用状态、超时、错误边界、检索元数据与受控分发键。
- 用边界测试保护“目录提供事实，运行时消费条目”的依赖方向。

**Non-Goals:**

- 不增加能力管理界面、HTTP 管理接口、迁移或种子数据。
- 不做向量检索、意图识别、澄清、确认提议、结构化 Agent Call、授权或实际分发。
- 不修改现有 `/api/v1/llm/chat`，不引入 Redis、Task Management、SubAgent、Workflow 或 Harness。

## Decisions

### 1. 复用既有目录，而不是为 V2 新建表或注册中心

`platform_capability` 已满足 V2 所需的描述和可见性信息。P2.1 将它作为唯一事实来源，后续消费者通过 `CapabilityCatalogPort` 查询；`AgentRuntime` 只筛选 `agent` 类型，不能维护第二份能力目录。

替代方案是在 Dialogue 或 Gateway 中维护单独的能力列表。这会使权限、确认策略和输入 Schema 出现多份来源，也会让未来 Workflow 注册再次分叉，因此不采用。

### 2. 目录负责静态受控性和运行时可见性，不负责一次调用的决策或执行

目录在加载时保持对能力记录及受控 `dispatch_key` 的校验，读取时只返回启用且权限匹配的条目。它不根据用户自然语言选择能力，不验证一次请求的输入，不产生确认状态，也不调用任何目标 Use Case。

该分界允许 P2.2 用目录做候选来源，P2.3 和 P2.4 处理确认与结构化调用，P2.5/P2.6 再在执行路径重新校验当前目录、权限与输入。将这些职责直接放入目录会把读取服务变成编排入口，无法独立演化。

### 3. 分发键保留为不可执行的受控标识

`dispatch_key` 仍仅是稳定、可校验的代码标识，不保存 URL、类名、函数名或可由模型生成的执行地址。Composition Root 中的静态绑定继续用于启动期配置校验；真正的处理器选择和执行结果属于后续受控分发 change。

替代方案是让目录存储可执行地址。这会将数据库数据转化为任意执行入口，不符合现有安全边界，因此不采用。

### 4. 以架构测试保护最小边界

在既有目录集成测试之外，增加测试确保目录领域、端口和应用服务不依赖 Dialogue Runtime 或 Agent Runtime 的具体实现；同时确保 Agent Runtime 通过目录端口读取并且只处理 `agent` 条目。该测试不限制 Composition Root，因为具体实现只能在那里组装。

## Risks / Trade-offs

- [目录中的已启用能力缺少当前分发目标] -> 启动期静态校验继续报错；后续实际分发也必须重新核验，不能把目录查询结果视为执行授权。
- [后续模块绕过端口直接查询 ORM] -> 用架构测试和后续 change 的端口依赖约束阻止平行事实来源。
- [未来出现 Workflow 或 SubAgent 类型] -> 本 change 不扩展枚举；后续独立 change 在确认其目录语义和受控分发方式后再扩展，避免预先引入未使用的类型。

## Migration Plan

无需数据迁移或接口迁移。现有表、种子数据和 V1 交互链路保持不变；若新增边界测试揭示既有依赖错误，只回退对应代码调整，不删除目录数据。

## Open Questions

无。Workflow 与 SubAgent 的目录表达方式留给实际引入它们的独立 change 决定。
