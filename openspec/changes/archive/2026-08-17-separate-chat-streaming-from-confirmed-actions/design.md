## Context

当前 Chat 页面先调用 `POST /api/v1/interaction/intent`。统一网关会为每个已匹配能力创建确认提议，忽略目录中的 `confirmation_policy`；因此普通 `chat.general` 也必须批准。页面不再调用既有 SSE Chat 接口，原有的增量渲染队列没有输入，回答只能完整返回后一次性展示。

目标是在不让浏览器决定执行路径的前提下，恢复普通对话的真实流式输出。Agent、文件、外部系统和其他要求批准的能力不能因该调整绕过现有的服务端提议、主体绑定和受控分发边界。

## Goals / Non-Goals

**Goals:**

- 由目录确认策略驱动服务端分流，`chat.general` 无需批准即可受控执行。
- 新增一个同时承载路由结果和 Chat SSE 增量的服务端入口。
- 让 Chat 页面恢复逐增量展示，并继续在同一消息流中展示澄清、批准、取消和失败。
- 保持已有直接 Chat HTTP 契约及确认接口兼容。

**Non-Goals:**

- 不允许浏览器声明能力代码、确认策略、权限或分发目标。
- 不将 Agent、文件处理、写入、外部调用或当前其他目录能力改为自动执行。
- 不实现 Agent 执行过程流式化、条件规则表达式、会话持久化或新的模型 Provider。

## Decisions

### 1. 使用服务端控制的交互 SSE 入口

新增 `POST /api/v1/interaction/chat/stream`，请求体沿用 `user_input` 与 `provided_inputs`。入口先经过候选召回、结构化识别、可信主体权限过滤和目录复核，再决定输出分支：

- `chat.general` 且策略为 `never`：调用现有 `StreamingChatApplication`，输出 `meta`、`delta`、`complete` 事件。
- 策略为 `always` 或当前无条件规则的 `conditional`：创建短期提议，输出一次 `approval_required` 事件后关闭流，不调用目标能力。
- 澄清、未识别、拒绝或无需流式的受控完成：输出一次 `result` 事件后关闭流。

浏览器不接收分发键、完整提议输入、权限或 Provider 对象。它只依据受控事件渲染消息、批准卡或错误状态。

选择统一入口而不是“浏览器先请求识别，再自行调用 `/llm/chat/stream`”，因为后者让客户端拥有路由决定权，并使后续低风险能力的策略难以统一审计。保留既有直接 Chat SSE 接口，供旧客户端和独立接口测试继续使用。

### 2. 确认策略以保守方式生效

`never` 代表目录明确授权的无批准执行；分流前和执行前仍重新校验启用状态、权限及输入契约。`always` 必须创建提议。`conditional` 目前没有受控条件表达式，因此按 `always` 处理，避免未定义条件导致自动执行。

首版仅将 `chat.general` 的种子与现有数据库记录更新为 `never`。其他已登记能力保持 `always`，包括知识检索、政策判断和 Tender Agent。

选择目录策略而不是在前端硬编码“普通聊天无需批准”，因为风险边界应与能力注册信息一同受控、可审计并可在未来用户权限模块接入后复用。

### 3. Chat 前端复用既有 SSE 解析与增量渲染队列

页面新增交互流 API/Hook，复用专用流式 HTTP 客户端和 `useDeltaRenderQueue`。对 `meta`、`delta`、`complete` 事件恢复连接中、输出中、排空后完成的状态；对 `approval_required` 和 `result` 事件渲染受控交互结果。取消操作中止当前 SSE 请求；批准卡仍调用既有确认接口。

不采用“完整答案返回后再逐字动画”的方案，因为它不能降低首字等待时间，只是伪造流式效果。

### 4. 流式 Chat 分发保持在应用层边界

新增 Application 层交互流服务，组合已有识别、确认、目录和流式 Chat Application。HTTP Route 仅负责把 RequestPrincipal 与请求 Schema 转为命令并序列化 SSE；Composition Root 注入已有 Ports/Use Case。通用受控 Dispatcher 继续只处理完整结果；流式 Chat 是 `llm.chat` 的专用、明确分支，不把异步流或 Provider 对象泄漏到通用 Dispatcher。

## Risks / Trade-offs

- [结构化识别先于首个 Chat token，增加首字等待] → 页面在连接中显示处理中状态；保留候选索引刷新和超时边界。
- [目录误将高风险能力设为 `never`] → 首版只迁移 `chat.general`；`conditional` 保守按批准处理；目录更新仍受受控管理。
- [SSE 在路由后或输出中发生 Provider 失败] → 响应开始前映射为稳定 HTTP 错误，开始后发送稳定 `error` 事件，不泄漏 Provider 原文。
- [取消时继续占用流资源] → 复用现有 AbortController、流关闭和并发槽释放逻辑。
- [既有调用方依赖直接 Chat] → 不删除或改变 `/api/v1/llm/chat`、`/api/v1/llm/chat/stream` 与确认接口。

## Migration Plan

1. 添加幂等 SQL 迁移，将现有 `chat.general` 记录更新为 `never`，并同步新安装种子。
2. 部署服务端交互流后，先由自动化测试验证普通 Chat 没有提议且批准类能力不执行。
3. 切换 Chat 页面至交互流；若入口异常，保留现有直连 Chat API 作为开发排障接口，不在浏览器静默绕过服务端路由。
4. 回滚时恢复前端到上一个已发布版本，并将 `chat.general` 策略恢复为 `always`；直接 Chat 接口不受影响。

## Open Questions

无。`conditional` 的动态条件规则、Agent 流式进度和更多无批准能力留待后续 Change。
