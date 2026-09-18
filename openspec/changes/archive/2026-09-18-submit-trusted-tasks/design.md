## Context

TM-02 已将 Task 聚合持久化到 PostgreSQL，但创建命令仍位于通用生命周期服务，调用方能够传入 task type、最大尝试次数、手动重试策略和 owner。系统尚无任务创建 HTTP 接口或业务接入，因此现在需要先收紧服务端内部的生产者边界，而不是把通用创建能力暴露给浏览器或 Agent 协议。

现有 Security 能力可提供经过协议适配器解析的 `RequestPrincipal`。Task 的 PostgreSQL Repository 已负责创建幂等和原子持久化，TM-03 不需要修改状态机、表结构或事务边界。

## Goals / Non-Goals

**Goals:**

- 提供供服务端业务 Application 调用的受信任 Task 提交能力。
- 仅接受已认证主体导出的 owner，拒绝匿名、未认证或无 subject 的提交。
- 由 Composition 注册的提交档案固定任务类别、最大尝试次数、手动重试策略和展示元数据字段白名单。
- 保持 TM-02 的提交唯一键与重放语义，并让后续 Tender 接入可以直接复用该能力。
- 通过架构测试禁止业务 Application 绕过受信任提交入口导入低层创建命令或生命周期服务。

**Non-Goals:**

- 不新增任务创建、查询、取消或重试 HTTP 路由，不新增 MCP 或 Function Calling 契约。
- 不实现 Worker、领取、lease 签发/续租、恢复扫描或任务执行器。
- 不注册 Tender 或其他真实业务提交者，不实现业务输入到 input fingerprint 的计算。
- 不修改 PostgreSQL 表、SQL 迁移、Task 状态机、Event 安全字段或 TaskView。
- 不实现真实身份认证或用户模块；复用现有 `RequestPrincipal` 契约。

## Decisions

### 以受信任主体确定 owner

`TrustedTaskSubmissionService` 接收 `RequestPrincipal` 和不含 owner/task type/策略字段的提交命令。服务要求 `authenticated=True` 且 subject 为非空字符串，并使用该 subject 作为 Task owner。这样 HTTP 或业务协议未来只能把已解析的主体传入，不能用请求体覆盖资源归属。

替代方案是保留 `owner_subject` 在命令中并约定调用方不要滥用。该方案无法在 Task Application 内验证归属来源，因此不采用。TM-03 不要求权限字符串，因为哪些主体可以提交哪类业务任务必须等实际业务生产者加入时再定义。

### 以 Composition 注册提交档案固定策略

新增不可变的提交档案，其中包含 task type、最大尝试次数、手动重试开关和允许的展示字段。受信任提交服务只能从其构造时注入的档案构造低层 `SubmitTaskCommand`；提交命令只带幂等键、输入指纹和展示元数据。未知展示字段、非字符串展示值和无效档案在进入 Repository 前被拒绝。

档案由 `app/composition/task.py` 的构造函数传入，不从 HTTP、数据库、环境变量或客户端配置读取。替代方案是全局可变注册表；它会引入运行时注册顺序和跨测试污染，当前没有多任务类型生产者，故不采用。

### 将通用生命周期提交限制为 Task 内部实现细节

保留 `TaskLifecycleService` 和既有 `SubmitTaskCommand` 作为受信任提交能力的内部编排依赖，避免改变 TM-01/TM-02 已验证的生命周期事务语义。业务 Application 面向 `TrustedTaskSubmissionService`，架构测试禁止 `app/business` 导入低层创建命令或生命周期服务；未来生产者由 Composition 显式组装该受限服务。

替代方案是立刻删除通用提交方法或将所有生命周期命令拆散。那会无谓扩大 TM-03 的变更面，并影响 TM-04 执行器契约，因此不采用。

### 不增加协议和持久化适配器

TM-03 是内部 Application 能力，没有接口层路由、公开 Schema 或前端调用。服务将固定档案和可信 owner 转换为现有生命周期命令，继续由 TM-02 PostgreSQL Repository 处理幂等创建、唯一冲突回读和事务提交。不会新增表、迁移或外部 Provider。

## Risks / Trade-offs

- [业务代码直接导入低层生命周期类] → 架构 AST 检查只允许业务层使用受信任提交能力；实际业务接入时再次通过代码评审和测试约束。
- [错误地把客户端数据当作可信主体] → 服务仅消费 `RequestPrincipal`，协议适配器仍必须按既有 Security 机制解析主体；TM-03 不增加绕过该机制的 HTTP 入口。
- [提交档案与实际业务策略不符] → 当前只提供显式构造函数与合成测试档案；TM-07 注册 Tender 前再创建独立 Change 固化其策略。
- [重放语义被二次实现而漂移] → 服务只委托 TM-02 已有 `TaskLifecycleService.submit`，不另建提交表或幂等算法。

## Migration Plan

1. 新增受信任提交契约、档案校验、Application 服务和 Composition 构造函数。
2. 以测试替身和隔离 PostgreSQL schema 验证主体、策略、元数据与重放语义。
3. 更新架构基线、看板和主规格，完成验证后归档 TM-03。
4. 回滚时停止构造受信任提交服务；TM-02 已持久化的 Task 不受影响，且无需数据库回滚。

## Open Questions

无。每种真实业务任务的提交档案和 input fingerprint 生成规则属于其接入 Change，而非 TM-03。
