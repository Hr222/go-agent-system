# Frontend Architecture

## 1. 文档定位

本文档描述项目独立前端应用的工程结构、技术选型、页面边界、请求规范和演进方向。

本文档与根目录的 `ARCHITECTURE.md` 对齐，前端作为独立的应用层存在，通过稳定的 HTTP API 与后端交互。

前端不直接依赖 GLM、LangChain 或 LangGraph 的具体实现，只依赖后端提供的业务接口。

本文档描述长期工程架构，不记录某个阶段的完成进度、验收结果或当前是否已经实现。阶段范围、实施状态和验收证据分别记录在 `docs/` 下对应的工作进度文档中。

## 2. 前端职责

| 职责 | 说明 |
|---|---|
| LLM Chat 界面 | 提供独立的通用 LLM 对话入口，展示消息、加载状态、错误和重试 |
| Agent 工作台 | 提供 Agent 选择、任务创建、任务状态和结果展示 |
| 知识库界面 | 管理知识库、上传文档、查看处理状态和执行检索 |
| Tender Agent | 提供投标书相关任务入口和结果预览 |
| 用户交互 | 处理上传、表单、进度、错误、重试和下载 |
| API 调用 | 通过统一 Axios 客户端访问后端 |
| 状态管理 | 管理页面状态、服务端状态和异步任务状态 |
| 类型约束 | 使用 TypeScript 保证前后端数据结构清晰 |

前端不负责：

| 不负责内容 | 归属 |
|---|---|
| GLM 调用 | 后端 LLM 层 |
| LangChain 组装 | 后端应用或编排层 |
| LangGraph 编排 | 后续后端 Agent 编排层 |
| Function Calling / MCP | 后端 Agent Runtime 和协议适配层 |
| Agent / SubAgent 协作 | 后端 Agent Runtime |
| 会话记忆和上下文持久化 | 后端 Conversation 能力 |
| 文档解析和向量化 | 后端知识库能力 |
| 投标书业务规则 | 后端 Tender Agent |
| 数据库访问 | 后端基础设施层 |

## 3. 技术选型

| 层级 | 选型 | 约束 |
|---|---|---|
| 框架 | React 18 | 复用现有工程 |
| 开发语言 | TypeScript | `strict: true` |
| 构建工具 | Vite | 复用现有 Vite 工程 |
| JavaScript 标准 | ES2022 | 使用现代 ES8+ 语法 |
| UI 组件库 | Ant Design 5 | 支持企业级工作台和文档管理 |
| 图标 | lucide-react | 保持现代、简洁的视觉风格 |
| 路由 | React Router | 管理 Chat、Agent、知识库和任务页面 |
| HTTP 客户端 | Axios | 统一请求、错误、超时和上传进度 |
| 服务端状态 | TanStack React Query | 缓存、轮询、重试和请求状态 |
| 表单校验 | Ant Design Form + Zod | 兼顾交互和运行时校验 |
| 样式 | Ant Design Token + CSS Modules | 支持主题定制和局部隔离 |
| 单元测试 | Vitest + React Testing Library | 测试组件和业务交互 |
| 端到端测试 | Playwright | 测试上传、任务和下载链路 |

不使用原生 `fetch` 作为项目请求入口，也不再额外封装 Fetch。

## 4. 工程边界

项目已经存在 `frontend` 前端工程，后续只在该工程内进行改造。

| 约束 | 要求 |
|---|---|
| 前端工程 | 继续使用现有 `frontend` |
| 包管理 | 不新建第二套前端包 |
| 配置文件 | 在现有 Vite、TypeScript 配置基础上调整 |
| 依赖管理 | 只允许修改现有 `frontend/package.json` |
| 现有组件 | 逐步重构和复用，不直接废弃 |
| 后端接口 | 保持现有接口能力，新增功能需先明确契约 |
| UI 改造 | 采用渐进式改造，避免一次性重写 |

现有 Mock 页面是正式系统界面的 UI 基线，不是需要整体废弃的临时产品页面。后续只替换其 Mock Data、Mock Action 和状态来源，逐步接入 Hook、业务 API 与真实后端状态。

## 5. 前端分层结构

```text
frontend/
└── src/
    ├── app/
    │   ├── router.tsx
    │   ├── providers.tsx
    │   └── appConfig.ts
    ├── layouts/
    │   └── AgentWorkspaceLayout.tsx
    ├── features/
    │   ├── chat/
    │   │   ├── pages/
    │   │   ├── hooks/
    │   │   ├── api/
    │   │   └── types.ts
    │   ├── knowledge-base/
    │   │   ├── pages/
    │   │   ├── components/
    │   │   ├── hooks/
    │   │   ├── api/
    │   │   └── types.ts
    │   └── agent/
    │       └── tender/
    │           ├── pages/
    │           ├── components/
    │           ├── hooks/
    │           ├── api/
    │           └── types.ts
    ├── services/
    │   └── http/
    │       ├── axiosClient.ts
    │       ├── errorHandler.ts
    │       └── requestTypes.ts
    ├── shared/
    │   ├── components/
    │   ├── constants/
    │   ├── types/
    │   └── utils/
    ├── styles/
    │   ├── theme.ts
    │   └── global.css
    └── main.tsx
```

现有的上传、检索、Chat 和结果组件应归属对应的业务模块，而不是继续全部集中在 `App.tsx`。

当前 `features/mock-workspace/` 承载的工作台页面属于正式界面基线。它可以在不改变用户界面的前提下逐步拆分到 `features/agent/*` 或其他业务模块中；目录名称不改变其产品定位。

## 6. 模块关系

```text
Application Workspace
├── LLM Chat
│   └── Generic Chat
├── Knowledge Base
│   ├── Knowledge Base List
│   ├── Document Upload
│   ├── Document Processing Status
│   └── Retrieval
└── Agents
    └── Tender Agent
        ├── Task Creation
        ├── Task Status
        ├── Optional Knowledge Base Selection
        └── Tender Skeleton Preview
```

知识库属于平台共享能力，不放入 `tender` 模块内部。

LLM Chat 是独立的通用能力入口，不属于任何一个 Agent。Agent 是否以对话方式参与交互，由后端 Agent Runtime 和具体产品用例决定；不要求每个 Agent 都提供一套 Chat 页面。

知识库选择不是所有 Agent 的固定前置步骤，是否展示和如何使用必须以后端 Agent 契约为准。

后续扩展财务或风控 Agent 时，保持以下结构：

```text
features/agent/
├── tender/
├── finance/
└── risk/
```

## 7. Axios 请求规范

所有后端请求必须经过统一 Axios Client。

```text
Page Component
    ↓
React Query Hook
    ↓
Business API
    ↓
Axios Client
    ↓
Backend API
```

| 能力 | 统一处理方式 |
|---|---|
| API 前缀 | 统一使用 `/api` |
| 超时 | Axios Client 统一配置 |
| 请求头 | 统一注入 |
| 认证信息 | 由请求拦截器预留 |
| 错误转换 | 响应拦截器转换为统一错误结构 |
| 文件上传 | 使用 Axios 上传进度回调 |
| 请求取消 | 使用 AbortSignal |
| 日志调试 | 在开发环境记录请求方法、路径和耗时 |
| 页面请求 | 不允许组件直接创建 Axios 请求 |

业务 API 只负责描述业务接口，不负责处理页面状态。

## 8. 状态管理规范

| 状态类型 | 管理方式 |
|---|---|
| 输入框、弹窗、Tab | React State |
| 后端数据 | TanStack React Query |
| 上传进度 | Axios 回调结合组件状态 |
| 异步任务状态 | React Query 轮询 |
| 跨页面临时状态 | 必要时使用 Zustand |
| 全局业务状态 | 默认不建立，避免过早引入复杂状态管理 |

前端不使用 Redux 作为默认状态管理方案。

## 9. 页面规划

| 页面 | 路由 | 主要能力 |
|---|---|---|
| 通用 LLM Chat | `/chat` | 发送消息、展示模型响应、加载状态、错误和重试 |
| Agent 工作台 | `/agents` | 查看 Agent 列表和运行状态 |
| Tender Agent | `/agents/tender` | 创建投标书处理任务 |
| Tender 任务详情 | `/agents/tender/tasks/:taskId` | 查看任务进度和结果 |
| Tender 骨架预览 | `/agents/tender/tasks/:taskId/skeleton` | 查看和下载章节骨架结果 |
| 知识库首页 | `/knowledge-bases` | 查看知识库列表 |
| 知识库详情 | `/knowledge-bases/:knowledgeBaseId` | 管理知识库文档 |
| 文档上传 | `/knowledge-bases/:knowledgeBaseId/documents/upload` | 上传和处理文件 |
| 知识库检索 | `/knowledge-bases/:knowledgeBaseId/search` | 执行检索并查看结果 |
| Workflow | `/workflow` | 预留入口，暂不实现复杂编排 |

## 10. 知识库前端边界

知识库是平台共享能力。前端负责知识库管理、文档处理状态和检索交互，不负责文档解析、向量化、索引构建或持久化实现。

| 能力 | 前端边界 |
|---|---|
| 知识库列表 | 展示名称、描述、文档数量、更新时间和状态 |
| 创建知识库 | 提供正式表单和校验 |
| 文档上传 | 支持拖拽、批量上传和上传进度 |
| 文档列表 | 展示文件名、类型、大小、处理状态和时间 |
| 处理状态 | 展示待处理、处理中、已完成和失败 |
| 失败处理 | 显示错误信息并支持重新处理 |
| 文档删除 | 提供明确确认和结果反馈 |
| 文档详情 | 查看文档元信息和处理状态 |
| 检索页面 | 统一搜索输入、结果卡片和来源文档展示 |
| 空状态 | 为无知识库、无文档、无检索结果提供引导 |

## 11. Agent 前端边界

Agent 前端模块负责具体 Agent 的用户入口、参数收集、任务状态和结果展示；不负责 Agent 编排、工具执行或模型调用。

```text
选择或上传文件
    ↓
创建 Tender 任务
    ↓
查询任务状态
    ↓
生成 Agent 结果
    ↓
预览结果
    ↓
下载结果
```

具体 Agent 可以采用同步响应、异步任务、流式事件或其他后端契约。Tender 的文件、任务、章节骨架等属于 Tender 自身的业务模型，不应上升为所有 Agent 的统一前端模型。

前端只面向 Agent/Application API，不直接绑定 GLM、LangChain、LangGraph、Function Calling 或 MCP。

通用 `/chat` 与 Agent 任务界面保持独立。只有当具体 Agent 的产品用例需要对话式交互时，才由后端提供相应 Agent 会话契约，前端再增加对应界面；不为每个 Agent 默认复制 Chat 能力。

## 12. UI 视觉方向

AetherFlow 作为视觉参考，但不直接复制其导出代码。

| 区域 | 设计方向 |
|---|---|
| 侧边栏 | 深色背景，展示 Agent 和平台模块 |
| 顶部导航 | 显示当前工作区、任务状态和用户信息 |
| 主工作区 | 浅色背景，突出任务和文档内容 |
| 卡片 | 圆角、弱边框、清晰层级 |
| 主色 | 蓝色或蓝绿色，用于操作和状态强调 |
| 状态色 | 成功、处理中、失败分别保持明确区分 |
| 文档树 | 使用 Tree 展示章节层级 |
| 响应式 | 优先适配桌面端，保留平板可用性 |
| 可读性 | 深色区域不承载大段正文内容 |

## 13. TypeScript 规范

| 规则 | 要求 |
|---|---|
| 类型检查 | 开启 `strict` |
| `any` | 默认禁止 |
| API 类型 | 请求和响应分别定义 |
| 组件 Props | 所有公共组件必须声明类型 |
| 状态值 | 使用联合类型或明确枚举 |
| 错误对象 | 使用统一错误类型 |
| 文件类型 | 区分浏览器 `File` 和后端文件记录 |
| 命名 | 组件使用 PascalCase，变量使用 camelCase |
| 导入 | 避免跨业务模块直接引用内部文件 |
| 模块边界 | 业务模块通过公共 API 或 shared 层交互 |

## 14. 架构约束检查

| 检查项 | 约束 |
|---|---|
| 工程 | 使用现有 `frontend`，不新建第二套前端工程 |
| 模块 | Chat、知识库和 Agent 按业务能力独立组织 |
| 请求 | 页面不直接创建 Axios 请求，统一经过 Hook、业务 API 和 HTTP Client |
| 依赖 | 前端不依赖 LLM Provider、LangChain、LangGraph、Function Calling 或 MCP 的实现细节 |
| Agent | 前端展示 Agent 契约，不承担 Agent Runtime 编排和工具执行 |
| 知识库 | 作为平台共享能力存在，不被某个 Agent 私有化 |
| Mock | Mock 仅替代数据和行为，不代表正式 UI 页面需要废弃 |
| 演进 | 新能力通过稳定 API 契约接入，优先渐进式替换现有实现 |

## 15. 架构范围外的实现细节

以下内容不属于前端架构的实现职责：

| 内容 | 原因 |
|---|---|
| LLM Provider 和模型客户端 | 属于后端 LLM 层 |
| LangChain / LangGraph 实现 | 属于后端适配或 Agent Runtime |
| Function Calling / MCP 执行 | 属于后端 Agent 协议和能力层 |
| Agent / SubAgent 编排 | 属于后端 Agent Runtime |
| 文档解析、向量化和数据库访问 | 属于后端知识库和基础设施层 |
| 会话历史、上下文记忆和持久化 | 属于后端 Conversation 能力 |

## 16. 与工作进度文档的关系

本文件只定义长期前端架构。以下内容必须记录在阶段工作进度文档中，而不应反向改变整体架构：

- 某个页面或 API 当前是否已经实现
- F1/F2 的工作范围、切片顺序和完成状态
- 前后端联调记录、测试结果和验收证据
- 当前使用真实数据还是 Mock Data
- 尚未实现的 Agent、任务或结果能力

前端作为独立应用层存在，Chat、知识库和 Agent 是并列的前端业务能力入口；知识库作为平台共享能力，Tender 作为 Agent 下的业务模块。前端通过稳定 API 与后端交互，不感知后端具体使用的 LLM、LangChain、LangGraph、Function Calling 或 MCP 实现。
