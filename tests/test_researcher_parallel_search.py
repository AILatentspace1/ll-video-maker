from __future__ import annotations

from ll_video_maker.agents.researcher import _normalize_queries


def test_normalize_queries_deduplicates_and_trims() -> None:
    queries = [
        " AI Agent 2026 ",
        "AI Agent 2026",
        "",
        "AI Agent comparison",
        "AI Agent market trends",
        "AI Agent expert review",
        "AI Agent statistics data",
        "ignored overflow",
    ]

    normalized = _normalize_queries(queries)

    assert normalized == [
        "AI Agent 2026",
        "AI Agent comparison",
        "AI Agent market trends",
        "AI Agent expert review",
        "AI Agent statistics data",
    ]

