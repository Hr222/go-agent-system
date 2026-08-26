from __future__ import annotations

# Prompt templates contain long natural-language lines by design.
# ruff: noqa: E501
import json

from app.business.agents.tender.contracts import (
    TenderAnalysis,
    TenderChunk,
    TenderChunkAnalysis,
)
from app.platform.llm.contracts import StructuredLlmRequest

TENDER_SKELETON_PROMPT_VERSION = "tender-skeleton-v1-boundary-copy-20260804"
TENDER_CHUNK_EXTRACT_PROMPT_VERSION = "tender-chunk-v1-compact-format-20260731"
TENDER_MERGE_PROMPT_VERSION = "tender-merge-v1-compact-format-20260731"
TENDER_BOUNDARY_VERIFY_PROMPT_VERSION = "tender-boundary-verify-v1-20260804"

TENDER_SKELETON_SYSTEM_PROMPT = """
你是一名投标师, 现在需要你从各种招标文件中查找招标文件中投标书需要的格式。

现在唯一目标是：从当前招标 DOCX 中找出招标人明确提供的投标文件格式，规划一份或多份可继续填写的投标骨架。\

必须遵守：
1. 先排除目录、目录页、页眉页脚、重复索引和“见第 X 章”的目录引用，再定位正文中的格式区域。章节编号不固定，优先寻找“投标文件格式”“响应文件格式”“投标文件组成”\
“附件：投标文件格式”等明确标题。
2. 格式区域内出现明确的“第一部分/第二部分”“商务技术标/经济标”“商务标/技术标/报价文件/资格文件”等分卷标题时，必须按正文中同级标题切分。\
分卷标题之前的内容不能被放进后一个分卷；目录中的同名标题不能作为边界。
3. 单卷只输出一份文件，多卷只按招标文件明确要求输出对应的独立装订、密封或电子提交文件。项目中标后的报告、评估成果、服务交付物不能作为投标文件分卷。
   公共附件、资格审查材料、承诺书和表格只有在原文明确要求独立提交时才能成为 output；否则归入所属分卷的 requirements，不得单独生成文件。
4. 必须返回整个格式区域的 format_start_block_id 和 format_end_block_id，以及每个 output 的 source_start_block_id 和 source_end_block_id；所有 ID 必须是源文档 evidence_id，不能省略，不能用代表性证据代替边界。
   单卷 output 通常覆盖格式区域的完整范围；多卷从第一个真实分册封面开始，到最后一个真实分册结束，前言/编制说明可以留在格式区域但不得作为分册。
5. 输出文件必须保留源文件中已有的标题、章节顺序、函件、表格、附件模板、封面和待填写占位。证据引用必须按源文档顺序列出，不能跨越到其他分卷。
   每个 output 的 evidence_refs 只能引用其自身边界内的代表性证据，不能制造跨卷引用。
6. 只能概括格式区中明确出现的文件组成和填写槽位。不要使用公司知识库，不要补写技术方案、公司名称、资质、业绩、人员、价格、服务承诺或任何公司事实。\
前置章节中仅有要求、没有格式模板的内容，留作后续阶段，不要塞入 V1 骨架。
7. 无法确认格式区域或分卷边界时，输出 needs_review，并列出冲突证据；不要猜测、合并或静默生成完整骨架。
8. 输出必须紧凑：summary 不超过 500 个字符，key_requirements 最多 24 条，outputs 最多 8 个，evidence 最多 32 条，uncertainties 和 risks 各最多 8 条。
9. evidence 的 quote 只摘录不超过 120 个字符的关键短语，location 只写简短位置；不要复制整段正文、表格或页眉页脚。
10. requirement 的 notes 每项最多 2 条且每条不超过 120 个字符；section_titles 每个 output 最多 40 条；所有 refs 去重且按源文档顺序排列。
11. requirement.kind 只能使用 composition、section、form、table、attachment、submission、placeholder 或 risk；不得填写 requirement、other 或自造枚举值。
12. 只返回符合 TenderAnalysis Schema 的 JSON object，不要返回 Markdown、代码块、思考过程或额外解释。
""".strip()


def build_tender_skeleton_request(
    *,
    source_text: str,
    user_focus: str | None = None,
) -> StructuredLlmRequest:
    focus_text = user_focus.strip() if user_focus and user_focus.strip() else "无额外关注点。"
    return StructuredLlmRequest(
        system_prompt=TENDER_SKELETON_SYSTEM_PROMPT,
        user_prompt=(
            "请按 V1 规则分析下面的招标文件证据，并返回 TenderAnalysis。\n\n"
            f"用户关注点：{focus_text}\n\n"
            "输出前逐项检查：是否排除了目录；是否使用正文格式标题；是否按明确分卷标题切分；"
            "每个 output 的 evidence_refs 是否只覆盖该分卷且保持源文档顺序。\n\n"
            "招标文件证据：\n"
            f"{source_text}"
        ),
        prompt_version=TENDER_SKELETON_PROMPT_VERSION,
    )


TENDER_BOUNDARY_VERIFY_SYSTEM_PROMPT = """
你是 Tender Agent 的格式边界复核器。

你只复核单卷投标文件格式区域的起止边界，不重新规划文件内容，不生成公司事实，不改变单卷结论。
检查 proposed_start_block_id 是否确实是格式章节标题或格式区域起点，检查 proposed_end_block_id 是否覆盖最后一个格式函件、表格或附件模板。
目录、目录引用、编制说明和中标后服务交付物不应成为格式边界。
如果边界正确，should_adjust=false，并保留 new_start_block_id/new_end_block_id 为空；如果边界错误，should_adjust=true，必须返回上下文中已有的准确 evidence_id。
只返回 TenderBoundaryVerification JSON object。
""".strip()


def build_tender_boundary_verification_request(
    *,
    boundary_context: str,
    proposed_start_block_id: str,
    proposed_end_block_id: str,
) -> StructuredLlmRequest:
    return StructuredLlmRequest(
        system_prompt=TENDER_BOUNDARY_VERIFY_SYSTEM_PROMPT,
        user_prompt=(
            f"拟议起点：{proposed_start_block_id}\n"
            f"拟议终点：{proposed_end_block_id}\n"
            "请复核下面的边界上下文，并按要求返回 TenderBoundaryVerification。\n\n"
            f"边界上下文：\n{boundary_context}"
        ),
        prompt_version=TENDER_BOUNDARY_VERIFY_PROMPT_VERSION,
    )


TENDER_CHUNK_EXTRACT_SYSTEM_PROMPT = """
你是 Tender Agent 的 V1 局部格式证据提取器。

只分析当前分块，不做全局结论。提取本分块中明确出现的投标文件格式标题、分卷标题、章节标题、函件、表格、附件模板、\
待填写槽位和提交规则，并保留本分块的 evidence_id。

规则：
- 目录、目录页、重复索引和页眉页脚只能作为“目录候选”记录，不能作为正式分卷边界或输出文件证据。
- 不要仅凭“商务、技术、经济、报价”等普通词语创建分卷；只有明确的格式区标题或同级分卷标题才可作为候选。\
- 不要在局部阶段决定整体单卷/多卷，也不要把前置章节的散落要求变成 V1 正文。
- 不得生成公司名称、资质、业绩、人员、价格或服务方案。
- 每条结果只能引用当前分块的 evidence_id；证据不足时记录 uncertainties。
- 输出必须紧凑：只保留会影响格式骨架的结果；requirements 最多 20 条，output_candidates 最多 8 条，submission_rules 最多 12 条，uncertainties 最多 8 条。
- evidence 只返回必要的证据 ID，每个 quote 只摘录不超过 120 个字符的关键短语，不要复制整段正文、表格或页眉页脚；location 只写简短位置。
- requirement 的 notes 每项最多 2 条且每条不超过 120 个字符；不要重复 evidence 中已有的原文。
- requirement.kind 只能使用 composition、section、form、table、attachment、submission、placeholder 或 risk；不得填写 requirement、other 或自造枚举值。
- 只返回 TenderChunkAnalysis JSON object。
""".strip()


TENDER_MERGE_SYSTEM_PROMPT = """
你是 Tender Agent 的 V1 格式边界归并器。

输入是同一份招标文件的局部格式证据。你的任务是归并为最终 TenderAnalysis，服务于“原样保留招标文件格式并生成骨架”，\
不是生成投标正文。

归并优先级：
1. 正文中明确的格式区域标题高于目录、目录引用、章节编号和行业惯例。
2. 正文中明确的同级分卷标题决定 output 边界。一个分卷从自己的标题开始，到下一个同级分卷标题之前结束；\
后一个分卷不得包含前一个分卷的章节、表格或函件。
3. 只有明确归属于某个分卷的证据才能放入该 output。公共封套或公共附件不能被误判为前一个或后一个分卷的正文；\
归属不明时标记 needs_review。
4. evidence_refs 必须去重、按源文档顺序排列，并只引用输入中已有的 evidence_id。\
   每个 output 尽量提供 source_start_block_id 和 source_end_block_id，二者必须来自输入中的 evidence_id。
- 归并输入和输出都必须保持紧凑：删除重复证据和重复说明；每条 evidence 的 quote 不超过 120 个字符，不复制整段正文。
- 只保留能影响 output 边界、章节、表格、附件和待填写槽位的 requirements；不要把普通说明扩写成 notes 或 summary。
保留跨分块冲突双方的证据，不能静默选择。
5. V1 只输出格式骨架所需的标题、函件、表格、附件和待填写槽位。前置章节的散落要求、公司资料、建议、\
资料不足项和知识库引用不属于当前任务。
- key_requirements 中的 kind 只能使用 composition、section、form、table、attachment、submission、placeholder 或 risk；不得填写 requirement、other 或自造枚举值。
6. 无法确认单卷/多卷或边界时，必须返回 needs_review，不能通过猜测补齐 output。
7. 只返回 TenderAnalysis JSON object，不要返回 Markdown、代码块、思考过程或额外解释。
""".strip()


def build_tender_chunk_request(
    *,
    chunk: TenderChunk,
    user_focus: str | None = None,
) -> StructuredLlmRequest:
    focus_text = user_focus.strip() if user_focus and user_focus.strip() else "无额外关注点。"
    heading_path = " / ".join(chunk.heading_path) or "未标明章节"
    return StructuredLlmRequest(
        system_prompt=TENDER_CHUNK_EXTRACT_SYSTEM_PROMPT,
        user_prompt=(
            f"分块 ID：{chunk.chunk_id}\n"
            f"章节路径：{heading_path}\n"
            f"当前分块允许引用的 evidence_id（只能从以下列表选择）：{', '.join(chunk.evidence_ids)}\n"
            f"用户关注点：{focus_text}\n"
            "请只分析当前分块，返回 TenderChunkAnalysis。\n"
            f"当前分块证据：\n{chunk.text}"
        ),
        prompt_version=TENDER_CHUNK_EXTRACT_PROMPT_VERSION,
    )


def build_tender_merge_request(
    *,
    items: tuple[TenderChunkAnalysis | TenderAnalysis, ...],
    batch_id: str,
) -> StructuredLlmRequest:
    serialized = [item.model_dump(mode="json") for item in items]
    return StructuredLlmRequest(
        system_prompt=TENDER_MERGE_SYSTEM_PROMPT,
        user_prompt=(
            f"归并批次：{batch_id}\n"
            "请根据 V1 格式边界规则归并以下局部结果。保留证据顺序，排除目录，"
            "并严格按正文中明确的同级分卷标题切分；每个 output 尽量输出 source_start_block_id 和 "
            "source_end_block_id。\n"
            f"结构化输入：{json.dumps(serialized, ensure_ascii=False)}"
        ),
        prompt_version=TENDER_MERGE_PROMPT_VERSION,
    )
