"""Tests for the agentic loop. Everything runs on the deterministic MockLLM."""

from scout.agent import ResearchAgent, _parse_json_list
from scout.llm import MockLLM


def _fake_tools(calls):
    def fake_search(query, max_results=3):
        calls.append(query)
        return [
            {
                "title": f"Result {i} for {query}",
                "url": f"https://example.com/{len(calls)}-{i}",
                "snippet": "a snippet",
            }
            for i in range(max_results)
        ]

    def fake_fetch(url, max_chars=8000):
        return {"url": url, "title": f"Page {url}", "text": "evidence text here"}

    return fake_search, fake_fetch


def test_full_loop_produces_cited_report():
    llm = MockLLM()
    queries: list[str] = []
    search_fn, fetch_fn = _fake_tools(queries)
    agent = ResearchAgent(
        llm,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        max_subquestions=2,
        results_per_query=2,
        max_refine_rounds=1,
    )
    report = agent.run("What is retrieval-augmented generation?")
    for section in ("## Summary", "## Key findings", "## Limitations", "## Sources"):
        assert section in report, f"missing {section}"
    assert "[1]" in report  # inline citation present
    assert "https://example.com/" in report  # source links present


def test_loop_refines_at_least_once():
    """The observer must trigger a refinement pass (agentic, not one-shot)."""
    llm = MockLLM()
    queries: list[str] = []
    search_fn, fetch_fn = _fake_tools(queries)
    agent = ResearchAgent(
        llm, search_fn=search_fn, fetch_fn=fetch_fn, max_subquestions=2,
        results_per_query=1, max_refine_rounds=1,
    )
    agent.run("some topic")
    # 2 sub-questions x (initial + 1 refinement) = 4 searches minimum
    assert len(queries) >= 4
    assert "OBSERVER" in llm.stages
    assert llm.stages.count("PLANNER") == 1
    assert llm.stages.count("SYNTHESIZER") == 1


def test_duplicate_urls_are_deduped():
    llm = MockLLM()

    def same_search(query, max_results=3):
        return [
            {"title": "Same", "url": "https://example.com/same", "snippet": "s"}
            for _ in range(max_results)
        ]

    def same_fetch(url, max_chars=8000):
        return {"url": url, "title": "Same", "text": "same text"}

    agent = ResearchAgent(
        llm, search_fn=same_search, fetch_fn=same_fetch, max_subquestions=3
    )
    report = agent.run("topic")
    assert report.count("https://example.com/same") == 1


def test_empty_evidence_still_returns_report():
    llm = MockLLM()
    agent = ResearchAgent(
        llm,
        search_fn=lambda q, n=3: [],
        fetch_fn=lambda u, m=8000: {"url": u, "title": "", "text": ""},
        max_subquestions=1,
    )
    report = agent.run("topic with no results")
    assert "## Sources" in report
    assert "(none)" in report


def test_parse_json_list_handles_noise():
    assert _parse_json_list('here is ["a", "b"] done') == ["a", "b"]
    assert _parse_json_list("no json here") == []
    assert _parse_json_list('["a", bad]') == []
