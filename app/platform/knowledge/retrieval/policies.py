from __future__ import annotations

import re
from dataclasses import dataclass, field

CHINESE_NUMERAL_FRAGMENT = r"[一二三四五六七八九十百千万零〇两0-9]+"

@dataclass(slots=True)
class RetrievalKeywordPlan:
    """关键词召回前的查询拆解结果。"""

    normalized_query: str
    focus_query: str
    keywords: list[str]
    priority_keywords: list[str] = field(default_factory=list)
    anchor_keywords: list[str] = field(default_factory=list)


class PolicyRetrievalQueryPolicy:
    """制度检索中的查询归一化与关键词提取规则。"""

    # TODO: 当前仍处于 MVP 阶段，这批规则先写死在领域层，方便快速验证效果。
    # 后续如果问题类型变多，或需要按业务线维护不同规则，再演进为可配置规则集。
    _question_phrases = (
        "在什么情况下",
        "什么情况下",
        "什么情形下",
        "什么时候",
        "要做什么",
        "该怎么做",
        "怎么处理",
        "如何处理",
        "如何计算",
        "怎么计算",
        "多久一次",
        "在哪里",
        "在哪儿",
        "哪些人",
        "哪些行为",
        "哪些",
        "什么人",
        "什么",
        "多久",
        "多长时间",
        "多长",
        "多少",
        "几个",
        "几级",
        "几天",
        "几个月",
        "是否",
        "吗",
        "么",
        "如何",
        "怎么",
        "怎么办",
        "有哪",
        "有哪些",
        "在哪",
        "哪里",
        "何时",
    )
    _year_pattern = re.compile(r"(?:19|20)\d{2}年?|(?:19|20)\d{2}(?:0[1-9]|1[0-2])")
    _article_pattern = re.compile(
        rf"第{CHINESE_NUMERAL_FRAGMENT}(?:章|节|条)"
    )
    _max_priority_span_size = 8
    _max_priority_keyword_count = 8
    _noise_terms = {
        "什么",
        "哪些",
        "多久",
        "多少",
        "是否",
        "如何",
        "怎么",
        "办法",
        "规定",
        "要求",
    }

    def build_keyword_plan(self, query: str) -> RetrievalKeywordPlan:
        normalized_query = self.normalize_query(query)
        focus_query = self._strip_question_shell(normalized_query)
        anchor_keywords = self._extract_anchor_keywords(focus_query)
        priority_keywords = self._extract_priority_keywords(
            normalized_query=normalized_query,
            focus_query=focus_query,
            anchor_keywords=anchor_keywords,
        )

        candidates: list[str] = []
        candidates.extend(priority_keywords)
        if len(focus_query) >= 2:
            candidates.append(focus_query)
        if focus_query != normalized_query and len(normalized_query) >= 2:
            candidates.append(normalized_query)
        for size in (4, 3, 2):
            for index in range(0, max(0, len(focus_query) - size + 1)):
                term = focus_query[index : index + size]
                if self.should_keep_keyword(term):
                    candidates.append(term)

        deduplicated_keywords: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            if item not in seen:
                deduplicated_keywords.append(item)
                seen.add(item)
            if len(deduplicated_keywords) >= 12:
                break

        return RetrievalKeywordPlan(
            normalized_query=normalized_query,
            focus_query=focus_query,
            keywords=deduplicated_keywords,
            priority_keywords=priority_keywords,
            anchor_keywords=anchor_keywords,
        )

    def normalize_query(self, query: str) -> str:
        return "".join(re.findall(r"[0-9a-zA-Z\u4e00-\u9fff]+", query.lower()))

    def should_keep_keyword(self, term: str) -> bool:
        if len(term) < 2:
            return False
        if re.fullmatch(r"(?:19|20)\d{2}", term):
            return True
        if term in self._noise_terms:
            return False
        if len(set(term)) == 1:
            return False
        return True

    def _strip_question_shell(self, normalized_query: str) -> str:
        focus_query = normalized_query
        for phrase in sorted(self._question_phrases, key=len, reverse=True):
            focus_query = focus_query.replace(phrase, "")
        return focus_query or normalized_query

    def _extract_priority_keywords(
        self,
        *,
        normalized_query: str,
        focus_query: str,
        anchor_keywords: list[str],
    ) -> list[str]:
        candidates: list[str] = []

        for pattern in (self._year_pattern, self._article_pattern):
            for match in pattern.finditer(normalized_query):
                term = match.group(0)
                if term.endswith("年") and len(term) == 5:
                    candidates.append(term)
                    candidates.append(term[:-1])
                else:
                    candidates.append(term)

        if len(focus_query) >= 4:
            candidates.append(focus_query)

        candidates.extend(anchor_keywords)
        candidates.extend(self._extract_informative_spans(focus_query))
        if focus_query != normalized_query:
            candidates.extend(self._extract_informative_spans(normalized_query))

        deduplicated: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                deduplicated.append(candidate)
                seen.add(candidate)
        return deduplicated[: self._max_priority_keyword_count]

    def _extract_anchor_keywords(self, text: str) -> list[str]:
        normalized_text = text.strip()
        if len(normalized_text) < 2:
            return []

        candidates: list[str] = []
        candidate_sizes: list[int] = []
        for size in (
            min(6, len(normalized_text)),
            min(4, len(normalized_text)),
            min(3, len(normalized_text)),
            2 if len(normalized_text) <= 6 else None,
        ):
            if size is None or size < 2 or size in candidate_sizes:
                continue
            candidate_sizes.append(size)

        for size in candidate_sizes:
            candidates.append(normalized_text[:size])
            candidates.append(normalized_text[-size:])

        deduplicated: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not self.should_keep_keyword(candidate):
                continue
            if candidate not in seen:
                deduplicated.append(candidate)
                seen.add(candidate)
        return deduplicated[:8]

    def _extract_informative_spans(self, text: str) -> list[str]:
        normalized_text = text.strip()
        if len(normalized_text) < 4:
            return []

        scored_spans: list[tuple[int, int, int, str]] = []
        max_span_size = min(self._max_priority_span_size, len(normalized_text))
        for size in range(max_span_size, 3, -1):
            for index in range(0, len(normalized_text) - size + 1):
                term = normalized_text[index : index + size]
                if not self.should_keep_keyword(term):
                    continue
                score = size * 10
                if any(char.isdigit() for char in term):
                    score += 20
                if index == 0 or index + size == len(normalized_text):
                    score += 3
                if term == normalized_text:
                    score += 5
                scored_spans.append((score, size, -index, term))

        scored_spans.sort(reverse=True)
        selected: list[str] = []
        for _, _, _, term in scored_spans:
            if term in selected:
                continue
            if any(term in existing for existing in selected if len(existing) >= len(term) + 2):
                continue
            selected.append(term)
            if len(selected) >= self._max_priority_keyword_count:
                break
        return selected
