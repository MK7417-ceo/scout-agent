"""Tests for the LLM provider abstraction (mock + Groq). All offline."""

import json

import pytest
import requests

from scout.llm import GroqLLM, MockLLM


def _system(messages, stage):
    return [
        {"role": "system", "content": f"You are the {stage} of a research agent."},
    ]


def test_mock_planner_returns_subquestions():
    llm = MockLLM()
    out = llm.chat(
        _system(None, "PLANNER") + [{"role": "user", "content": "TOPIC: black holes"}]
    )
    subqs = json.loads(out)
    assert len(subqs) == 3
    assert all("black holes" in q for q in subqs)


def test_mock_observer_forces_one_refinement():
    llm = MockLLM()
    first = json.loads(
        llm.chat(
            _system(None, "OBSERVER")
            + [
                {
                    "role": "user",
                    "content": "SUB-QUESTION: What is RAG?\nROUND: 0\nRESULTS:\n- x",
                }
            ]
        )
    )
    assert first["sufficient"] is False
    assert first["refined_query"]

    second = json.loads(
        llm.chat(
            _system(None, "OBSERVER")
            + [
                {
                    "role": "user",
                    "content": "SUB-QUESTION: What is RAG?\nROUND: 1\nRESULTS:\n- x",
                }
            ]
        )
    )
    assert second["sufficient"] is True


def test_mock_synthesizer_cites_sources():
    llm = MockLLM()
    user = (
        "TOPIC: RAG\nEVIDENCE:\n"
        "[1] Some Title — https://example.com/a\n"
        "    Excerpt: RAG combines retrieval with generation.\n"
    )
    report = llm.chat(_system(None, "SYNTHESIZER") + [{"role": "user", "content": user}])
    assert report.startswith("# Research report: RAG")
    assert "## Summary" in report
    assert "## Key findings" in report
    assert "## Limitations" in report
    assert "## Sources" in report
    assert "[1]" in report
    assert "https://example.com/a" in report


def test_mock_synthesizer_empty_evidence():
    llm = MockLLM()
    report = llm.chat(
        _system(None, "SYNTHESIZER")
        + [{"role": "user", "content": "TOPIC: RAG\nEVIDENCE:\n"}]
    )
    assert "## Sources" in report
    assert "(none)" in report


def test_groq_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        GroqLLM()


def test_groq_posts_to_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-a-secret")
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "hello from groq"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)
    llm = GroqLLM(model="some-model")
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert out == "hello from groq"
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key-not-a-secret"
    assert captured["json"]["model"] == "some-model"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hi"}]
