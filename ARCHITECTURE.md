# 架构文档索引

本项目按架构迭代维护独立基线，避免将已实现事实和未来演化目标混在同一文件中。

| 文档 | 状态 | 用途 |
|---|---|---|
| [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) | 已完成基线 | 当前已实现的平台分层、模块职责、依赖方向与 V1 HTTP/MCP 链路。 |
| [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) | 已定稿，待实施 | 完整 LLM 对话体系：Conversation、多轮 Dialogue、Context Builder、Gateway 授权和单 Agent 调用。 |

## 使用规则

- 修改已经存在的模块、接口和依赖时，以 `ARCHITECTURE_V1.md` 为事实基线。
- 设计或实施 LLM 多轮对话体系时，以 `ARCHITECTURE_V2.md` 为目标基线，并通过独立 OpenSpec Change 逐步落地。
- V2 的规划不表示对应模块、接口、数据表或 Provider 已经实现。
- 首个 V2 Change 是 `conversation-foundation`；其后依次演化 Dialogue Runtime、Interaction Gateway 与 Agent Call 授权。
- `/api/v1/llm/chat` 仅是 V1 快速入口。新 Dialogue API 验收后，删除该入口及其前端调用、Schema 和测试，不保留兼容后门。
