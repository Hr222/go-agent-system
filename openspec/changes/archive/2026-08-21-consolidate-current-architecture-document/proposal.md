## Why

项目尚未正式上线，但架构事实、已确认的对话演化方向和前端工程边界被拆分在 `ARCHITECTURE.md`、`ARCHITECTURE_V1.md`、`ARCHITECTURE_V2.md` 与 `FRONTEND_ARCHITECTURE.md` 中。开发者需要先判断版本再拼接上下文，容易把历史说明、当前实现和未来边界混为实施依据。

现在统一为一个当前架构基线，可以在真实上线和版本治理开始前消除 V1/V2 的人为分叉，并删除已完全合并的旧架构文档。

## What Changes

- 将 `ARCHITECTURE.md` 改为项目唯一的当前全系统架构基线，合并后端平台分层、LLM 对话体系、主体与会话归属边界、附件与知识库边界，以及前端工程分层。
- 在统一文档中明确每层职责、允许依赖、禁止事项、当前总体结构、多轮请求流程、代码目录和已实现/未实现边界。
- 删除已被 `ARCHITECTURE.md` 完整吸收的 `ARCHITECTURE_V1.md`、`ARCHITECTURE_V2.md` 和 `FRONTEND_ARCHITECTURE.md`。
- 更新协作说明、OpenSpec 配置和当前阶段文档中的架构引用，使其只指向统一基线。
- 不修改运行时代码、HTTP 契约、数据库、依赖、部署配置或现有 OpenSpec 规格。

## Capabilities

### New Capabilities

- `current-architecture-baseline`: 定义当前唯一架构基线的文档职责、内容边界和历史文档使用规则。

### Modified Capabilities

无。该 Change 不改变任何运行时能力的行为要求。

## Impact

- 文档：`ARCHITECTURE.md`、`agent.md`、`openspec/config.yaml`、`openspec/README.md` 和当前阶段文档；删除三份旧架构文档。
- 开发流程：后续 Change、设计和实现只以 `ARCHITECTURE.md` 作为架构依据。
- 兼容性：不影响 HTTP、持久化、状态流转、外部 Provider、安全实现或敏感数据处理。
