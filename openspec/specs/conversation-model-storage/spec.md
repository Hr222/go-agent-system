# conversation-model-storage Specification

## Purpose
TBD - created by archiving change conversation-model-storage. Update Purpose after archive.
## Requirements
### Requirement: 会话与消息基础记录可持久化
系统 MUST 能够将 Conversation 与 Message 作为独立记录持久化到 PostgreSQL。每个 Conversation MUST 具有稳定的 UUID 标识和创建、更新时间；每个 Message MUST 具有稳定的 UUID 标识、所属 Conversation 标识、角色、内容、顺序号和创建时间。

#### Scenario: 持久化并恢复一条有效消息
- **WHEN** 基础设施层保存一个具有有效 UUID、角色、非空内容和正整数顺序号的 Conversation 与 Message
- **THEN** 系统 MUST 能够从持久化记录恢复相同的会话标识、消息标识、角色、内容和顺序号
- **AND** 恢复后的消息 MUST 仍关联到原 Conversation

#### Scenario: 消息引用不存在的会话
- **WHEN** 基础设施层尝试持久化 `conversation_id` 不存在的 Message
- **THEN** 数据库 MUST 拒绝该记录
- **AND** 系统 MUST 不留下孤立消息记录

### Requirement: 消息基础不变量受持久化约束保护
系统 MUST 在领域模型和数据库层保护 Message 的最小不变量：角色仅能是 `system`、`user` 或 `assistant`；内容去除首尾空白后不得为空；顺序号必须大于零；同一 Conversation 内的顺序号不得重复。

#### Scenario: 持久化不支持的消息角色
- **WHEN** 尝试持久化角色不属于 `system`、`user`、`assistant` 的 Message
- **THEN** 系统 MUST 拒绝该 Message
- **AND** 数据库 MUST 不保存无效角色记录

#### Scenario: 持久化空白内容或非正顺序号
- **WHEN** 尝试持久化内容为空白，或顺序号小于等于零的 Message
- **THEN** 系统 MUST 拒绝该 Message
- **AND** 已存在的有效消息 MUST 保持不变

#### Scenario: 同一会话出现重复顺序号
- **WHEN** 同一 Conversation 已存在顺序号为 `n` 的 Message，且再次尝试持久化顺序号为 `n` 的另一条 Message
- **THEN** 数据库 MUST 拒绝第二条 Message
- **AND** 不同 Conversation 可以各自保存顺序号为 `n` 的 Message

### Requirement: 会话模型存储不引入对话行为
系统 MUST 将 Conversation 模型存储限制在领域模型、ORM 映射、数据库脚本和转换边界内，不得通过本能力新增会话创建接口、消息追加接口、历史查询接口、LLM 调用、Agent 调用或前端交互。

#### Scenario: 初始化模型存储后访问统一对话入口
- **WHEN** 部署仅包含 Conversation 模型存储的版本
- **THEN** `/api/v1/interaction/chat/stream` 继续是浏览器对话入口
- **AND** 系统 MUST 不新增可供客户端调用的 Conversation HTTP 路由
