## Context

当前 `app/modules` 使用单一目录承载平台能力、业务应用和业务 Agent。模块内部已经采用 `application`、`domain`、`ports` 的边界，但顶层包名无法表达产品结构：`online` 看起来与 `knowledge`、`llm` 同属业务模块，`tender` 看起来像平台核心，`interaction` 同时包含能力目录、Gateway 和 Agent 调用策略。

本 Change 只调整 Python 包的物理归属和导入路径。现有应用契约、HTTP 路由、MCP、Function Calling、数据库模型、Provider 适配器和业务处理行为保持不变。

## Goals / Non-Goals

**Goals:**

- 用 `platform` 表达可复用的 Agent 开发平台能力。
- 用 `business` 表达具体业务应用和业务 Agent。
- 保持能力目录在 `interaction` 模块中的现有物理结构，同时让整个模块归入平台能力层。
- 保留模块内部的 Domain、Application、Ports 边界以及横向技术层。
- 让 Composition Root 明确组装平台能力和业务能力，且平台层不反向依赖业务层。
- 通过导入扫描、结构测试和全量测试证明行为未改变。

**Non-Goals:**

- 不实现 Task Management、Workflow、SubAgent、低代码编辑器或真实用户模块。
- 不在本 Change 中重新设计动态 Pipeline 配置；`ingestion` 作为平台模块保留，政策知识库仍是当前验证样本。
- 不改变上下文压缩与摘要的功能实现；按其已经完成作为平台前置能力处理。
- 不把当前 Tender 业务 Agent 扩展成通用 Agent 编排运行时。
- 不修改 HTTP 路由、数据库 Schema、外部协议字段或前端页面行为。

## Decisions

### 1. 使用平台层和业务层表达产品归属

目标包结构为：

```text
app/
├── platform/
│   ├── llm/
│   ├── knowledge/
│   ├── ingestion/
│   ├── conversation/
│   ├── dialogue/
│   ├── interaction/
│   ├── attachment/
│   ├── security/
│   └── agent/
│       └── runtime/
├── business/
│   ├── online/
│   └── agents/
│       └── tender/
├── interfaces/
├── infrastructure/
├── composition/
└── shared/
```

`platform` 和 `business` 表达领域归属；`interfaces`、`infrastructure`、`composition`、`shared` 表达横向技术职责。二者不再混在同一层级。

替代方案是仅给现有模块改名，继续放在 `modules/` 下。该方案不能解决平台与业务语义混合的问题，因此不采用。

### 2. 保留现有模块内部边界

`interaction` 内部继续同时承载 Platform Capability Catalog、Gateway、意图识别、确认和受控分发；`conversation` 内部继续承载会话、消息、事件、访问控制、上下文构建和摘要。此次只改变它们位于 `platform` 下的物理路径，不拆分职责，不修改公开模块契约。

`dialogue` 继续负责一轮对话运行，依赖 Conversation 的稳定应用契约，不直接依赖数据库或 Provider。`agent/runtime` 迁移到 `platform/agent/runtime`，继续从现有能力目录读取 Agent 条目并执行固定映射。

### 3. Ingestion 保持平台归属

现有 `ingestion` 整体迁移为 `platform/ingestion/`。当前代码中的政策命名表示第一种验证样本，不改变 Ingestion Pipeline 的平台能力归属，也不在此 Change 中引入资料类型插件或动态配置模型。

### 4. 业务应用只依赖平台能力

`online` 迁移为 `business/online/`，使用 `platform/knowledge` 和 `platform/llm` 提供政策知识问答、规则检索和业务判断。`agent/tender` 迁移为 `business/agents/tender/`，由 `platform/agent/runtime` 受控执行；当前 Tender 使用结构化 LLM 和附件能力，但不因目录迁移自动获得 Knowledge 依赖。

### 5. 采用一次性导入迁移，不保留长期兼容别名

实现时按包依赖图批量更新导入、导出、Composition Root、接口适配器和测试。完成后删除旧的 `app/modules` 物理路径，避免新旧包并存形成第二套事实来源。由于不改变外部协议，迁移不需要数据库迁移或 API 版本兼容层。

## Risks / Trade-offs

- [大量导入路径同时变化] → 先建立完整迁移清单，再用 AST 导入扫描、架构测试、全量后端测试和前端构建验证。
- [目录名称被误认为运行时行为变化] → 明确本 Change 不改公开契约、状态流转和业务结果，并在 Composition Root 中保持原有固定绑定。
- [平台与业务包迁移时出现循环依赖] → 保留现有模块内部依赖关系；平台层不导入业务层，具体业务与适配器绑定继续集中在 Composition Root。
- [当前政策命名仍存在于 Ingestion/Infrastructure] → 本 Change 只解决模块归属，不进行没有真实需求支撑的资料模型泛化；在架构文档中说明当前政策样本边界。

## Migration Plan

1. 创建目标包目录并迁移模块文件，先保持每个模块内部相对结构。
2. 按平台能力、业务应用、Composition Root、Interfaces、Tests 的顺序更新导入和导出。
3. 更新 `interaction`、`conversation`、`dialogue` 和 `agent/runtime` 的新包路径引用，但不拆分模块内部文件。
4. 删除旧包路径，运行 AST 边界检查、结构测试、后端测试、OpenSpec 校验和前端构建。
5. 代码 Change 验收后，执行架构文档 Change，文档中的目录和调用关系只引用迁移后的实际结构。

回滚方式：在未发布数据库或外部接口变化的前提下，使用版本回滚恢复旧包路径；不需要数据回滚。

## Open Questions

- 是否将 `composition` 进一步拆成 `composition/platform` 和 `composition/business`，由实施时的依赖规模决定；不得改变 Composition Root 的横向职责。
