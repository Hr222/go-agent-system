# Go Agent System

Go Agent System 是一个面向 Agent 开发的平台型应用。它将 LLM、Knowledge/RAG、通用资料处理、对话、交互、Agent Management、附件和安全能力组合起来，为具体业务 Agent 和业务应用提供可复用的运行基础。

详细的模块边界、依赖方向、运行时链路和物理目录以 [`ARCHITECTURE.md`](ARCHITECTURE.md) 为准。本 README 只负责项目定位、能力概览和使用导航。

## 项目背景

项目从知识库检索和业务资料处理开始，关注可追溯证据、可验证结果和受控的 Agent 调用。典型业务链路为：

```text
业务资料 / 招标文件
  -> 解析、清洗、OCR 与结构化处理
  -> Knowledge/RAG 入库与发布
  -> 检索、引用与证据判断
  -> 对话、规则判断或受控 Agent 调用
```

当前仓库包含 Python 后端、React/TypeScript 前端、PostgreSQL/pgvector 本地基础设施，以及多个 OpenAI 兼容的 LLM Provider 适配器。

## 当前能力

### 平台能力

- 通用资料处理 Pipeline：文件读取、格式解析、OCR、清洗、结构提取、分块、Embedding 和 Knowledge 写入。
- Knowledge/RAG：向量检索、关键词检索、结果融合、排序、版本发布、引用和证据不足处理。
- LLM：文本 Chat、流式 Chat、结构化输出、Embedding、Provider 适配、重试和请求治理。
- Conversation 与 Dialogue：会话创建、历史读写、事件记录、多轮上下文、流式回答和 Agent 结果续写。
- Interaction Gateway：自然语言能力识别、输入复核、权限校验、确认提议和受控分发。
- Agent Management：平台能力目录、Agent 调用策略、固定分发和 Agent Runtime。
- Attachment：上传、访问绑定、读取、存储和业务结果下载。

### 业务应用

- `online`：通过 Knowledge/RAG 提供知识问答、检索和规则判断能力。
- `agents/tender`：读取招标 DOCX，执行结构化分析、分块处理、投标骨架规划和文档渲染。

## 环境要求

- Python 3.11 或更高版本
- Node.js 和 npm
- Docker Desktop
- PostgreSQL 17 与 pgvector，推荐使用仓库提供的 Docker Compose
- 可选的外部服务凭据：
  - `GITEE_API_KEY`：Embedding
  - `ZHIPU_API_KEY`：GLM
  - `DEEPSEEK_API_KEY`：DeepSeek
  - `TENCENT_OCR_SECRET_ID` / `TENCENT_OCR_SECRET_KEY`：腾讯 OCR

## 本地运行

### 1. 安装后端依赖

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Linux/macOS：

```bash
source .venv/bin/activate
```

### 2. 创建本地配置

```powershell
Copy-Item .env.example .env
```

至少检查以下配置：

- `DATABASE_URL` 或 `POSTGRES_*`：数据库连接
- `GITEE_API_KEY`：Embedding 服务
- `LLM_PROVIDER` 及对应的 `ZHIPU_API_KEY` 或 `DEEPSEEK_API_KEY`
- `REQUEST_PRINCIPAL_MODE`、`STATIC_PRINCIPAL_SUBJECT`、`STATIC_PRINCIPAL_PERMISSIONS`：本地请求主体
- 腾讯 OCR 凭据：仅在需要真实 OCR 时配置

`.env.example` 中的静态主体仅适用于受控本地开发。密钥、数据库凭据、真实业务资料、OCR 原始响应和运行产物不得提交到 Git。

### 3. 启动 PostgreSQL

```powershell
docker compose --env-file .env -f docker/postgres/docker-compose.yml up -d
```

数据库初始化脚本位于 `docker/postgres/init/` 和 `sql/`。后端启动时会检查知识库表结构，但不会自动修改已有数据库结构。

### 4. 启动后端

在项目根目录执行：

```powershell
python -m app.run
```

默认监听 `127.0.0.1:9205`。

### 5. 启动前端

另开一个终端：

```powershell
Set-Location frontend
npm install
npm run dev
```

前端开发服务器默认监听 `127.0.0.1:5426`，并将 `/api` 请求代理到后端。

## 接口访问

默认地址如下；如果修改了 `.env` 中的 `BACKEND_HOST` 或 `BACKEND_PORT`，以配置值为准。

| 用途 | 地址 |
|---|---|
| 前端工作台 | <http://127.0.0.1:5426> |
| 后端根地址 | <http://127.0.0.1:9205/> |
| Swagger UI | <http://127.0.0.1:9205/docs> |
| ReDoc | <http://127.0.0.1:9205/redoc> |
| OpenAPI JSON | <http://127.0.0.1:9205/openapi.json> |
| 健康检查 | `GET /api/v1/health` |
| 就绪检查 | `GET /api/v1/ready` |
| Tender MCP | `http://127.0.0.1:9205/api/v1/mcp/tender/mcp` |

主要接口分组：

| 分组 | 主要路径 |
|---|---|
| 知识库管理 | `/api/v1/kb/*` |
| 资料处理与入库 | `/api/v1/kb/policy-ingestion/*`、`/api/v1/kb/policy-pipeline/*` |
| 检索与问答 | `/api/v1/kb/retrieval/search`、`/api/v1/kb/retrieval/ask` |
| 知识发布 | `/api/v1/kb/publication/activate` |
| 规则判断 | `/api/v1/kb/policy-decisions/{scenario_code}/review` |
| 统一交互 | `/api/v1/interaction/*` |
| 会话 | `/api/v1/conversations/*` |
| 附件 | `/api/v1/attachments/*` |

Swagger UI 和 OpenAPI JSON 是 HTTP 参数、响应结构和接口状态的直接参考。统一对话流使用 SSE，反向代理需要关闭响应缓冲并保持长连接。

## 常用检查命令

```powershell
python -m pytest -q
ruff check app tests
python -m compileall -q app tests
```

前端：

```powershell
Set-Location frontend
npm run test
npm run build
```

知识库只读审计：

```powershell
python -m app.scripts.run_knowledge_base_audit
```

## 目录结构

```text
app/
├── platform/             # 可复用的平台能力
│   ├── agent/             # Agent Runtime
│   ├── attachment/       # 附件能力
│   ├── conversation/      # 会话、历史和上下文
│   ├── dialogue/          # 对话编排和 Agent 结果续写
│   ├── ingestion/         # 通用资料处理 Pipeline
│   ├── interaction/       # Gateway、目录、确认和分发
│   ├── knowledge/         # Knowledge/RAG
│   ├── llm/               # LLM 契约和应用能力
│   └── security/          # 请求主体和安全边界
├── business/              # 业务应用
│   ├── online/            # Knowledge/RAG 业务应用
│   └── agents/tender/     # Tender 业务 Agent
├── interfaces/            # HTTP、MCP 和其他协议适配器
├── infrastructure/       # 数据库、Provider、OCR、文件适配器
├── composition/           # Composition Root 与固定绑定
└── shared/                # 配置、日志、异常和共享基础能力

frontend/                  # React / TypeScript 前端
tests/                     # 单元、应用、协议和架构边界测试
openspec/                  # 需求变更与交付产物
docs/                      # 系统看板、设计说明和业务资料
tools/                     # 人工诊断、验收和样本处理脚本
sql/                       # 数据库初始化和结构脚本
docker/                    # 本地基础设施配置
.runtime/                  # 本地运行产物，不提交到 Git
```

## 相关文档

- [`ARCHITECTURE.md`](ARCHITECTURE.md)：当前唯一的系统技术架构基线。
- [`agent.md`](agent.md)：协作、工程开发、测试、安全和提交约定。
- [`openspec/README.md`](openspec/README.md)：OpenSpec 变更、规格和验收流程。
- [`openspec/config.yaml`](openspec/config.yaml)：OpenSpec 项目配置。
- [`docs/go agent system - 系统看板.md`](docs/go%20agent%20system%20-%20系统看板.md)：项目实际进度和优先级。
- [`tools/ocr/README.md`](tools/ocr/README.md)：OCR 与样本分类工具说明。

真实业务文件、工具输出和运行时资料只能放在仓库外部或 `.runtime/`，不要放入测试资产或提交到 Git。
