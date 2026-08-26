from __future__ import annotations

from app.platform.knowledge.retrieval.policies import PolicyRetrievalQueryPolicy


def test_build_keyword_plan_keeps_year_and_document_type_as_priority_keywords() -> None:
    policy = PolicyRetrievalQueryPolicy()

    plan = policy.build_keyword_plan("2024年纳税证明在哪里")

    assert plan.focus_query == "2024年纳税证明"
    assert "2024年" in plan.priority_keywords
    assert "2024" in plan.priority_keywords
    assert "2024年纳税证明" in plan.priority_keywords
    assert plan.keywords[0] == "2024年"


def test_build_keyword_plan_removes_longer_question_shells_before_shorter_ones() -> None:
    policy = PolicyRetrievalQueryPolicy()

    plan = policy.build_keyword_plan("员工什么时候发工资")

    assert "什么时候" not in plan.focus_query
    assert plan.focus_query == "员工发工资"


def test_build_keyword_plan_extracts_informative_spans_without_domain_whitelist() -> None:
    policy = PolicyRetrievalQueryPolicy()

    plan = policy.build_keyword_plan("一般纳税人证明")

    assert "一般纳税人证明" in plan.priority_keywords
    assert any(keyword.startswith("一般纳税") for keyword in plan.priority_keywords)


def test_build_keyword_plan_keeps_short_suffix_anchor_for_natural_language_question() -> None:
    policy = PolicyRetrievalQueryPolicy()

    plan = policy.build_keyword_plan("什么情况下员工会被表彰")

    assert "表彰" in plan.anchor_keywords
