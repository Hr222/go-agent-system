from __future__ import annotations

import re
from collections import Counter

from app.platform.ingestion.contracts import AssembledLine, CleanedTextResult, ParsedTextResult


class PolicyTextCleaner:
    """在尽量不改变原意的前提下，对文本执行保守清洗。"""

    def clean(self, parsed_text: ParsedTextResult) -> CleanedTextResult:
        """
        步骤 6：规范空白字符，并移除低价值噪音。

        这里刻意保持保守，因为后续章节拆分依赖原始章、节、条结构不被破坏。
        """
        normalized_lines: list[AssembledLine] = []
        for item in parsed_text.lines:
            text = item.text.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
            for raw_line in text.split("\n"):
                normalized = re.sub(r"[ \t]+", " ", raw_line).strip()
                normalized_lines.append(
                    AssembledLine(
                        text=normalized,
                        page_no=item.page_no,
                        source_block_order=item.source_block_order,
                    )
                )

        repeated_noise = self._detect_repeated_noise([line.text for line in normalized_lines])
        removed_noise_examples: list[str] = []
        cleaned_lines: list[AssembledLine] = []
        blank_streak = 0

        for line in normalized_lines:
            if not line.text:
                blank_streak += 1
                if blank_streak <= 1:
                    cleaned_lines.append(line)
                continue

            blank_streak = 0
            if line.text in repeated_noise:
                removed_noise_examples.append(line.text)
                continue
            if re.fullmatch(r"第\s*\d+\s*页", line.text) or re.fullmatch(r"-\s*\d+\s*-", line.text):
                removed_noise_examples.append(line.text)
                continue
            cleaned_lines.append(line)

        return CleanedTextResult(
            clean_text="\n".join(line.text for line in cleaned_lines).strip(),
            page_count=parsed_text.page_count,
            lines=cleaned_lines,
            removed_noise_examples=removed_noise_examples[:10],
            notes=[
                "当前只做保守清洗。",
                "章、节、条编号会被刻意保留。",
            ],
        )

    def _detect_repeated_noise(self, lines: list[str]) -> set[str]:
        """
        启发式识别疑似页眉、页脚的重复短行。

        这里只删除重复出现多次的短文本，避免误删真实业务内容。
        """
        counter = Counter(line for line in lines if line and len(line) <= 30)
        return {line for line, count in counter.items() if count >= 3}
