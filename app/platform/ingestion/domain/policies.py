from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CHINESE_NUMERAL_FRAGMENT = r"[一二三四五六七八九十百千万零〇两0-9]+"
HeadingLevel = Literal[1, 2, 3]

@dataclass(slots=True)
class PolicyIntakeDecision:
    """领域层的准入决策对象。"""

    is_allowed: bool
    detected_file_kind: str
    needs_normalization: bool
    recommended_parse_method: str
    warnings: list[str]


class PolicyIntakePolicy:
    """制度文档准入规则。"""

    _image_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
    }
    _allowed_extensions = {".doc", ".docx", ".pdf", *_image_extensions}
    _excluded_keywords = {
        "身份证",
        "签字",
        "签名",
        "公章",
        "法人章",
        "印章",
        "账号",
        "密码",
        "联系方式",
        "联系",
        "logo",
        "照片",
        "截图",
        "盖章",
        "空白",
        "模板",
    }

    def decide(self, *, file_name: str, extension: str, size_bytes: int) -> PolicyIntakeDecision:
        if extension not in self._allowed_extensions:
            return PolicyIntakeDecision(
                is_allowed=False,
                detected_file_kind="unsupported",
                needs_normalization=False,
                recommended_parse_method="skip",
                warnings=["当前 MVP 仅允许 .doc/.docx/.pdf 以及常见图片扫描件文件。"],
            )

        if size_bytes <= 0:
            return PolicyIntakeDecision(
                is_allowed=False,
                detected_file_kind="empty",
                needs_normalization=False,
                recommended_parse_method="skip",
                warnings=["源文件为空。"],
            )

        lower_name = file_name.lower()
        for keyword in self._excluded_keywords:
            if keyword.lower() in lower_name:
                return PolicyIntakeDecision(
                    is_allowed=False,
                    detected_file_kind="excluded_by_keyword",
                    needs_normalization=False,
                    recommended_parse_method="skip",
                    warnings=[f"文件名命中排除关键词：{keyword}"],
                )

        if extension == ".doc":
            return PolicyIntakeDecision(
                is_allowed=True,
                detected_file_kind="word_legacy",
                needs_normalization=True,
                recommended_parse_method="doc",
                warnings=["旧版 .doc 文件会先转换为 .docx，再进入后续解析流程。"],
            )

        if extension == ".docx":
            return PolicyIntakeDecision(
                is_allowed=True,
                detected_file_kind="word_openxml",
                needs_normalization=False,
                recommended_parse_method="docx",
                warnings=[],
            )

        if extension in self._image_extensions:
            return PolicyIntakeDecision(
                is_allowed=True,
                detected_file_kind="image_scan",
                needs_normalization=False,
                recommended_parse_method="image",
                warnings=["图片文件将直接进入 OCR 流程。"],
            )

        return PolicyIntakeDecision(
            is_allowed=True,
            detected_file_kind="pdf",
            needs_normalization=False,
            recommended_parse_method="pdf",
            warnings=[],
        )


class PolicyIdentityPolicy:
    """根据文件名推导制度名称和版本标签。"""

    _bracket_noise_pattern = re.compile(
        r"[（(][^）)]{0,40}(模板|空白|盖章|签字|签名|扫描)[^）)]{0,40}[）)]"
    )

    def build_version_label(self, *, explicit_label: str | None, modified_at_text: str) -> str:
        if explicit_label:
            return explicit_label
        return modified_at_text

    def guess_policy_name(self, *, file_name: str) -> str:
        stem = file_name.rsplit(".", maxsplit=1)[0]
        cleaned = re.sub(r"^\d{6,8}", "", stem)
        cleaned = self._bracket_noise_pattern.sub("", cleaned)
        cleaned = cleaned.replace("--", "-").replace("_", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"-{2,}", "-", cleaned)
        return cleaned.strip(" -_") or stem


@dataclass(slots=True)
class SectionHeading:
    section_no: str
    section_title: str
    section_level: HeadingLevel


class PolicySectionStructurePolicy:
    """章节标题识别规则。"""

    _chapter_pattern = re.compile(rf"^(第{CHINESE_NUMERAL_FRAGMENT}章)\s*(.*)$")
    _section_pattern = re.compile(rf"^(第{CHINESE_NUMERAL_FRAGMENT}节)\s*(.*)$")
    _article_pattern = re.compile(rf"^(第{CHINESE_NUMERAL_FRAGMENT}条)\s*(.*)$")
    _body_punctuation_pattern = re.compile(r"[，。；：！？]")
    _article_title_max_length = 18
    _generic_title_max_length = 40

    def match_heading(self, line: str) -> SectionHeading | None:
        stripped = line.strip()
        for pattern, level in (
            (self._chapter_pattern, 1),
            (self._section_pattern, 2),
            (self._article_pattern, 3),
        ):
            match = pattern.match(stripped)
            if match:
                section_no = match.group(1)
                raw_title = match.group(2).strip()
                return SectionHeading(
                    section_no=section_no,
                    section_title=self._resolve_section_title(
                        section_no=section_no,
                        raw_title=raw_title,
                        level=level,
                    ),
                    section_level=level,
                )
        return None

    def rebuild_path(self, *, current_path: list[str], heading: SectionHeading) -> list[str]:
        if heading.section_level <= 1:
            return [heading.section_title]
        if len(current_path) < heading.section_level - 1:
            return current_path + [heading.section_title]
        return current_path[: heading.section_level - 1] + [heading.section_title]

    def _resolve_section_title(
        self,
        *,
        section_no: str,
        raw_title: str,
        level: HeadingLevel,
    ) -> str:
        if not raw_title:
            return section_no

        title = re.sub(r"\s+", " ", raw_title).strip()
        if not title:
            return section_no

        if level == 3 and self._looks_like_article_body(title):
            return section_no
        if (
            len(title) > self._generic_title_max_length
            and self._body_punctuation_pattern.search(title)
        ):
            return section_no
        return title

    def _looks_like_article_body(self, title: str) -> bool:
        return (
            len(title) > self._article_title_max_length
            or self._body_punctuation_pattern.search(title) is not None
        )


@dataclass(slots=True)
class ChunkSlice:
    start: int
    end: int
    text: str
    chunk_in_section: int




class PolicyChunkingPolicy:
    """先保留 section 边界，再按长度切块的规则。"""

    def __init__(self, *, target_chars: int, overlap_chars: int) -> None:
        if target_chars <= 0:
            raise ValueError("target_chars 必须大于 0。")
        if overlap_chars < 0:
            raise ValueError("overlap_chars 不能小于 0。")
        if overlap_chars >= target_chars:
            raise ValueError("overlap_chars 必须小于 target_chars。")

        self.target_chars = target_chars
        self.overlap_chars = overlap_chars

    def split_section_text(self, text: str) -> list[ChunkSlice]:
        """单个 section 过长时，再按长度切成多个片段。"""
        normalized = text.strip()
        if not normalized:
            return []
        if len(normalized) <= self.target_chars:
            return [ChunkSlice(start=0, end=len(normalized), text=normalized, chunk_in_section=0)]

        chunks: list[ChunkSlice] = []
        start = 0
        chunk_in_section = 0
        step = self.target_chars - self.overlap_chars
        while start < len(normalized):
            end = min(len(normalized), start + self.target_chars)
            if end < len(normalized):
                candidate = normalized[start:end]
                split_at = max(
                    candidate.rfind("\n"),
                    candidate.rfind("。"),
                    candidate.rfind("，"),
                )
                if split_at >= max(0, len(candidate) // 2):
                    end = start + split_at + 1
            chunk_text = normalized[start:end].strip()
            if chunk_text:
                chunks.append(
                    ChunkSlice(
                        start=start,
                        end=end,
                        text=chunk_text,
                        chunk_in_section=chunk_in_section,
                    )
                )
                chunk_in_section += 1
            if end >= len(normalized):
                break
            start = max(end - self.overlap_chars, start + step)
        return chunks
