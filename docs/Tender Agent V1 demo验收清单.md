# Tender Agent V1 demo 验收清单

## 目的与范围

本清单用于 V1 的外部样本回归。样本来自 `D:\workspace\bid-tech-generator\demo`，明确排除 `_skill_test`；不把旧 skill、目录名称、既有 `_skill_output` 或某个固定样本当作答案。单卷和多卷的最终分线必须以当前招标文件中明确的提交、分册、标包或合同要求为准。

当前已完成的是结构探针：20 个源 DOCX 均完成请求级读取、证据索引和分块规划；成功样本完成单/多输出渲染和生成 DOCX 重新打开检查，预算受限样本单独记录失败。样本选择只排除 `_skill_test`，不把 Demo3 或天津样本当作固定锚点。由于真实 GLM 大输入结构化调用仍可能超时，以下样本的“语义分线、章节归属和源文件要求覆盖”仍需真实模型或人工复核，不将结构探针结果冒充完整 V1.1 语义验收。

本轮 V1.1 已增加“索引 - 语义分块 - 局部要求提取 - 有界全局归并 - Schema 校验”链路。50MB 以内文件统一分块；70MB 为服务端硬拒绝线；解压总量、条目数和异常压缩比也在 LLM 调用前检查。V1.1 不包含 V2 公司资料库填充、异步任务、持久化索引或超大文件传输。

## 样本选择

| 编号 | 类型 | 分类 | 源招标文件 | 探针输出数 | 当前记录 |
| --- | --- | --- | --- | ---: | --- |
| S01 | 单卷 | 01_double_toc | `single/01_double_toc/2025-02-14 光大银行光华支行贷款抵押物价值评估服务采购项目/招标文件正文.docx` | 1 | 结构通过；语义待复核 |
| S02 | 单卷 | 01_double_toc | `single/01_double_toc/2025-04-29 中节能铁汉资产评估单一来源采购/单一来源采购文件-20250422.docx` | 1 | 结构通过；语义待复核 |
| S03 | 单卷 | 02_mostly_correct | `single/02_mostly_correct/20250326 中国民生银行股份有限公司北京分行押品价值评估机构入围项目（4.8截止）/押品价值评估服务入围项目-征询文件-发售稿.docx` | 1 | 结构通过；语义待复核 |
| S04 | 单卷 | 02_mostly_correct | `single/02_mostly_correct/2026-2-9 中国农业银行股份有限公司江西省分行信贷业务押品及不良资产评估机构采购项目（房产3.17）-流标/招标文件正文.docx` | 1 | 结构通过；语义待复核 |
| S05 | 单卷 | 03_appendix_missing | `single/03_appendix_missing/20250310 中国工商银行股份有限公司上海市分行2025至2027年不良贷款债权评估服务（3.28截止）/中国工商银行股份有限公司上海市分行2025至2027年不良贷款债权评估服务统一集中采购项目招标文件-发售稿.docx` | 1 | 结构通过；语义待复核 |
| S06 | 单卷 | 03_appendix_missing | `single/03_appendix_missing/20250908 江苏银行股份有限公司房地产、土地、资产评估机构入围采购项目（9.25）/江苏银行股份有限公司评估机构入围采购-发售稿.docx` | 1 | 结构通过；语义待复核 |
| S07 | 单卷 | 04_front_capture | `single/04_front_capture/01-招标文件下载(批量)/招标文件正文.docx` | 1 | 结构通过；语义待复核 |
| S08 | 单卷 | 04_front_capture | `single/04_front_capture/1-银行类_2/招标文件正文-副本.docx` | 1 | 结构通过；语义待复核 |
| S09 | 单卷 | 05_boundary_bleed | `single/05_boundary_bleed/20250521 渤海银行房地产评估公司入围采购项目竞争性采购公告/FUTC-2025-H037B_渤海银行房地产评估公司入围采购项目.docx` | 1 | 结构通过；语义待复核 |
| S10 | 单卷 | 06_structure_failure | `single/06_structure_failure/01 银行标_1/深圳农商银行招标邀请函-2025年存量抵押物及抵债资产价值重估服务项目.docx` | 1 | 结构通过；语义待复核 |
| M01 | 多卷 | multi | `multi/20240904 中国工商银行深圳市分行2024年普惠贷款押品评估服务项目-薛芳/中国工商银行深圳市分行2024年普惠贷款押品评估服务项目招标文件（最终版）.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M02 | 多卷 | multi | `multi/2025-11-20 长富金茂大厦2号楼物业价值评估项目/长富金茂大厦2号楼物业价值评估项目-A招标文件_V1.0.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M03 | 多卷 | multi | `multi/2025-12-8 中国建设银行股份有限公司湖南省分行抵押物评估服务采购项目（12.30）/中国建设银行股份有限公司湖南省分行抵押物评估服务采购项目招标文件.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M04 | 多卷 | multi | `multi/20250428 中国工商银行深圳市分行不良贷款批量转让评估服务项目（5.7号）/商务谈判通知书文件6--供应商须知及文件编制说明（线上）.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M05 | 多卷 | multi | `multi/20250828 中国邮政储蓄银行股份有限公司江苏省分行全省评估服务集中采购项目（9.16）/中国邮政储蓄银行股份有限公司江苏省分行全省评估服务集中采购项目招标文件.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M06 | 多卷 | multi | `multi/2026-02-09 天津津投租赁有限公司资产评估项目竞争性磋商文件/磋商文件-天津津投租赁有限公司资产评估项目竞争性磋商文件.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M07 | 多卷 | multi | `multi/2026-3-23 中国邮政储蓄银行股份有限公司福建省分行2026-2028年全省资产评估服务项目（4.13）（包9）/定稿 [招标文件]2026-2028年全省资产评估服务项目.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M08 | 多卷 | multi | `multi/2026-5-30 龙岗城投集团购买龙岗区某物业资产价值评估报告编制服务（6.22）/（招标）招标文件_YG26QG0038989-01_V1.0_招标文件.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M09 | 多卷 | multi | `multi/20260115 华夏银行杭州分行授信业务抵质押品评估外聘中介机构入围项目邀标书（2.3）吴一凡/华夏银行杭州分行授信业务抵质押品评估外聘中介机构入围项目邀标书.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |
| M10 | 多卷 | multi | `multi/20260211 兴业银行广州分行关于2026年外聘评估机构项目（3.4）/招标文件-兴业银行广州分行关于2026年外聘评估机构项目（以此为准）.docx` | 2（探针下限） | 结构通过；源文件分线待复核 |

## 每个样本的完整 V1 复核项

- 输出数量和文件名称：单卷必须 1 个；多卷按源文件明确的技术标、商务标、报价、标包或合同分线确定，不能按目录名猜测。
- 章节、表格、附件和占位：检查输出是否保留源文件明确结构，并把只有标题/要求而无正文的部分标为待填写位置。
- 服务交付成果边界：报告、评估成果等项目交付物不能仅因出现在项目范围中就被误判为投标文件分卷。
- 来源追溯：关键要求、分线、章节和待确认项均能指向当前招标文件的证据块。
- V1 边界：不出现公司资质、业绩、人员、价格或未经当前文件授权的事实；不调用公司资料库。
- 文件质量：每个返回 DOCX 可重新打开，且无本地临时路径、密钥或 Provider 原文泄露。

## 当前未验证项

1. 真实 GLM 结构化调用：最小 Chat 探针已通过；大输入 Tender 结构化请求仍可能因上游读取超时失败，未继续批量消耗 20 次模型调用。
2. 20 个样本的语义分线和章节归属：已完成 DOCX 结构探针，仍需可用的真实模型响应或人工逐项复核。
3. HTTP、MCP 与浏览器在真实模型配置下的端到端联调：Fake/协议测试通过，真实 Provider 联调待恢复后执行。

## GLM 真实调用诊断（2026-07-30）

- `python tools/llm_provider_diagnostics.py`：DNS、TCP、HTTPS `/models` 均通过；当前实际配置为 `https://open.bigmodel.cn/api/coding/paas/v4`、模型 `glm-5`，API Key 已配置但未输出。
- `python tools/llm_provider_diagnostics.py --chat`：最小普通 Chat 成功，约 7.3 秒返回 2 个字符。
- `python tools/llm_provider_diagnostics.py --chat --timeout 30`：本轮最小普通 Chat 成功，约 11.1 秒返回 2 个字符；DNS、TCP 和 HTTPS `/models` 均通过。
- 最小 OpenAI JSON Schema `chat.completions.parse` 对照：接口返回普通文本，SDK 本地 Pydantic 解析失败；不是网络故障。
- 最小 `response_format={"type":"json_object"}` 对照：成功，约 14.8 秒返回合法 JSON。
- Tender 原始 JSON Object 请求：输入约 40,498 字符，关闭 SDK 重试后 30 秒仍超时；应用实际调用每次 60 秒、自动重试两次，总耗时约 181.7 秒后返回 `APITimeoutError -> httpx.ReadTimeout -> httpcore.ReadTimeout`。
- 期间发现并修复了 LangChain `human` 消息到 GLM `user` 角色的映射；修复后不再出现 `400/1214 角色信息不正确`，但大输入请求仍超时。

## 本轮执行证据（2026-07-30）

- 结构探针命令：`python tools/tender_v1_sample_probe.py`（只排除 `_skill_test`，Reader 正常上限 50MB、硬拒绝线 70MB）
- 探针结果：20/20 样本均完成记录；19 个在 `planner + Fake 局部提取 + Fake 全局归并 + renderer` 链路结构通过，1 个因 128 分块上限稳定返回分析预算失败；单卷 10 个、多卷 10 个的记录均保留了 chunk/merge 调用数；成功输出均重新被 `python-docx` 打开。
- 语义结论：成功样本均明确标记为 `structural_pass_semantic_unverified`，失败样本单独记录为预算限制，没有把探针生成的确定性占位结果当作真实 LLM 语义验收。
- 自动化分块验收：Tender 相关 70 个测试通过，覆盖文本/表格边界、证据追溯、局部结果越界、有限重试、调用预算、ZIP 资源限制、HTTP 硬拒绝和 MCP 兼容入口。
- 单块真实 GLM 验收：`python tools/tender_chunk_smoke.py --timeout 15` 已确认请求进入 `tender-chunk-extract-v1`，但本次 GLM 在 15 秒内超时；Provider SDK 重试已关闭，未再产生隐式多次请求。
- 回归命令：后端 `pytest -q` 为 173 passed；`python -m compileall -q app tests tools` 通过；前端 `npm.cmd run test` 为 15 passed，`npm.cmd run build` 通过。
- 全量 Ruff：`ruff check app tests tools` 仍有 3 个既有 `tools/ocr/classify_sample_inventory.py`、`tools/ocr/tencent_ocr_mvp.py` 行长问题；本 Change 新增和修改范围的 Ruff 检查通过，未修改无关 OCR 工具。
- 浏览器单卷：上传 S01 类单卷样本，页面进入“正在分析并生成”，真实 GLM 请求约 182 秒后显示 `REQUEST_FAILED`；点击“重试”后重新进入提交中并再次显示同一错误。
- 浏览器多卷：上传天津多卷样本，页面进入“正在分析并生成”，真实 GLM 请求约 182 秒后显示 `REQUEST_FAILED`，没有展示伪造的分析结果或下载入口。
- HTTP/MCP：Fake Application 的成功、输入失败、Application 失败、资源返回和 Streamable HTTP 测试已通过；真实 Provider 成功结果和真实 DOCX 下载仍受上游超时阻塞。

## 归一化 Change 回测（2026-07-30）

- 已新增结构化 LLM 输出归一化装饰层：GLM 的直接 JSON、Schema 名称包装、Markdown JSON 代码块和独立思考字段均在目标 Schema 校验前处理；未来其他 Provider 可注册独立 Normalizer。
- `.env` 当前使用 `glm-5`。真实 GLM5 小分块调用约 9.9 秒成功；合成极小 DOCX 在明确单卷关注点后约 46.7 秒生成占位文件，但该输入不是真实招标文件，不能作为 V1 业务验收或交付物。
- 真实 Demo 单卷和多卷仍未完成：单卷样本在第 4 个分块连续超时，多卷样本在第 1 个大分块连续超时；另一份小文本 Demo 单卷因模型输出数量不符合单卷规则被正确拒绝。
- 当前结论：归一化层已通过自动化和小型真实调用验证，但 20 个 Demo 的真实语义分线、归并和骨架文件验收仍未通过，不能把 V1 标记为完成或归档。

## 最新验收安排（2026-08-05）

- 5.2 状态：用户已确认刚才归档的 Tender 分块 Change 已完成真实单卷、多卷验收；本 Change 复用该结果，DOCX 业务内容仍由用户人工确认。
- 5.3 MCP 探针：先启动后端，再分别运行 `python tools/tender_mcp_acceptance_probe.py <真实单卷.docx>` 和 `python tools/tender_mcp_acceptance_probe.py <真实多卷.docx>`。脚本通过 `/api/v1/mcp/tender/mcp` 调用 `tender.generate_bid_skeleton`，在样本目录下输出 `result.json` 和 DOCX 文件。
- 5.3 人工核对：只需确认脚本成功、分块/归并链路有结果、生成文件数量和文件可打开；DOCX 业务内容由用户自行核对。
- 5.4 前端入口：访问 `/agents/tender`，分别上传单卷和多卷样本，确认加载态、防重复提交、分析结果、所有文件下载、失败重试和无 `task_id`。
- 5.4 协议边界：前端验收使用现有 HTTP `/api/v1/agents/tender/skeleton`；MCP 协议入口由 5.3 单独验收，两者共享同一个 Tender Application。
- 2026-08-05 MCP 真实探针结果：单卷 `tmp/tender-mcp-acceptance/single-real/result.json` 返回 `ok`、`single_volume`、1 个 DOCX；多卷 `tmp/tender-mcp-acceptance/multi-real/result.json` 返回 `ok`、`multi_volume`、2 个 DOCX。生成 DOCX 均已通过 `python-docx` 重新打开检查，业务内容待用户人工核对。
- 2026-08-05 前端验收完成：用户确认真实单卷、多卷均可在 `http://127.0.0.1:5426/agents/tender` 完成上传、分析、结果展示和全部 DOCX 下载；加载态、防重复提交、失败重试和无 `task_id` 行为通过人工确认。
