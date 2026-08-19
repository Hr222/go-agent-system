# 架构文档索引

本项目按架构迭代维护独立基线，避免将已实现事实和未来演化目标混在同一文件中。

| 文档 | 状态 | 用途 |
|---|---|---|
| [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) | 已完成基线 | 当前已实现的平台分层、模块职责、依赖方向与 V1 HTTP/MCP 链路。 |
| [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) | 已定稿，实施中（已完成 P4） | 完整 LLM 对话体系：Conversation、多轮 Dialogue、Context Builder、Gateway 授权和单 Agent 调用。 |

## 使用规则

- 修改已经存在的模块、接口和依赖时，以 `ARCHITECTURE_V1.md` 为事实基线。
- 设计或实施 LLM 多轮对话体系时，以 `ARCHITECTURE_V2.md` 为目标基线，并通过独立 OpenSpec Change 逐步落地。
- V2 的目标架构并不表示所有模块、接口、数据表或 Provider 已经实现；已完成范围以归档的 OpenSpec Change 为准。
- V2 已完成 Conversation 基础、基础多轮 Dialogue、Interaction 控制、单 Agent 调用、Agent 结果续写和旧 V1 LLM Chat 入口退场。
- 浏览器对话统一使用 `/api/v1/interaction/chat/stream`；旧 `/api/v1/llm/chat` 及其流式变体已删除，不保留兼容后门。
