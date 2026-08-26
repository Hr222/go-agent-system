## Why

当前 `app/modules` 下的平台能力、业务应用和验证样例处于同一物理层级，代码实现虽然已经有较清晰的内部依赖边界，但目录名称无法表达 Go Agent System 作为低代码 Agent 开发平台的产品结构。尤其是 `interaction`、`agent`、`online`、`knowledge` 和 `ingestion` 的归属容易被误读，增加后续平台能力建设和业务 Agent 接入的维护成本。

## What Changes

- 建立 `platform` 与 `business` 两个明确的模块根目录。
- 将 LLM、Knowledge/RAG、Ingestion、Context、Gateway、Capability Catalog、Agent Management、Dialogue、Attachment 和 Security 归入平台能力层。
- 将 `online` 等具体业务应用，以及 Tender 业务 Agent 归入业务应用层。
- 保留 `interaction` 模块内部现有的 Gateway、能力目录、确认和分发结构，只改变其平台层物理归属。
- 保留各模块现有的 `application`、`domain`、`ports` 内部边界，主要调整包路径、导入关系和 Composition Root 组装位置。
- 保持现有 HTTP、MCP、Function Calling、数据库结构、Provider 行为和业务用例行为不变。
- 不在本 Change 中实现动态 Pipeline、Task Management、Workflow、SubAgent 或真实用户模块。
- 不在本 Change 中拆分 `interaction` 内部模块，也不重命名 `conversation`；这些属于后续独立重构。

## Capabilities

### New Capabilities

无。本 Change 只调整物理模块边界和依赖表达，不新增运行时业务能力。

### Modified Capabilities

无。本 Change 不改变已有能力的外部行为或需求契约。

## Impact

- 影响 `app/modules/` 下的包路径、模块导出和跨模块导入。
- 影响 `app/composition/` 的依赖组装、能力目录绑定和 ApplicationContainer 引用。
- 影响架构边界测试、模块结构测试以及相关测试导入路径。
- 不改变 HTTP 路由、请求响应模型、MCP 工具、Function Calling 契约或数据库 Schema。
- 不改变 `ingestion` 的平台能力归属；当前政策知识库继续作为其验证样本。
- 需要在本 Change 完成后，再以实际目录和依赖结果为依据更新 `ARCHITECTURE.md`。
