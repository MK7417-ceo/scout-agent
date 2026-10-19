"""LLM provider abstraction.

Two providers, one interface:

- ``MockLLM``  — deterministic, offline fake. Drives the full agent loop
  with zero network calls and zero API keys. Used by tests and the demo.
- ``GroqLLM``  — Groq's OpenAI-compatible chat endpoint (free tier).
  API key is read ONLY from the ``GROQ_API_KEY`` environment variable.
  It is never hardcoded, never logged, and never committed.
"""

from __future__ import annotations

import json
import os
import re

import requests

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class LLMProvider:
    """Minimal chat interface every provider implements."""

    def chat(self, messages: list[dict], **kwargs) -> str:
        raise NotImplementedError


class MockLLM(LLMProvider):
    """Deterministic fake LLM for tests and the offline demo.

    It inspects the system prompt to decide which agent stage is calling
    (PLANNER / OBSERVER / SYNTHESIZER) and returns a canned, deterministic
    response derived from the user's message. No network, no keys.
    """

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []
        self.stages: list[str] = []

    def _stage_of(self, messages: list[dict]) -> str:
        system = " ".join(
            m.get("content", "") for m in messages if m.get("role") == "system"
        )
        for stage in ("PLANNER", "OBSERVER", "SYNTHESIZER"):
            if stage in system:
                return stage
        return "UNKNOWN"

    def _user_text(self, messages: list[dict]) -> str:
        return "\n".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )

    def chat(self, messages: list[dict], **kwargs) -> str:
        stage = self._stage_of(messages)
        self.calls.append(messages)
        self.stages.append(stage)
        user = self._user_text(messages)
        if stage == "PLANNER":
            return self._plan(user)
        if stage == "OBSERVER":
            return self._observe(user)
        if stage == "SYNTHESIZER":
            return self._synthesize(user)
        return "mock-response"

    # -- stage implementations -------------------------------------------

    @staticmethod
    def _topic_of(user: str) -> str:
        m = re.search(r"^TOPIC:\s*(.+)$", user, re.M)
        return m.group(1).strip() if m else "the topic"

    def _plan(self, user: str) -> str:
        topic = self._topic_of(user)
        # Avoid "What is What is X?" when the topic itself is phrased as a question.
        clean = re.sub(r"^(what\s+is|what\s+are)\s+", "", topic, flags=re.I)
        clean = clean.rstrip("?").strip() or topic
        subqs = [
            f"What is {clean}?",
            f"How does {clean} work in practice?",
            f"What are the main use cases and limitations of {clean}?",
        ]
        return json.dumps(subqs)

    def _observe(self, user: str) -> str:
        m = re.search(r"^ROUND:\s*(\d+)", user, re.M)
        rnd = int(m.group(1)) if m else 0
        q = re.search(r"^SUB-QUESTION:\s*(.+)$", user, re.M)
        subq = q.group(1).strip() if q else "the question"
        if rnd == 0:
            # First pass is never "good enough": force one refinement round
            # so the loop demonstrably iterates.
            return json.dumps(
                {
                    "sufficient": False,
                    "refined_query": f"{subq} overview explained",
                    "reason": "results are thin; trying a broader query",
                }
            )
        return json.dumps(
            {"sufficient": True, "refined_query": "", "reason": "results cover the question"}
        )

    def _synthesize(self, user: str) -> str:
        topic = self._topic_of(user)
        items = re.findall(
            r"^\[(\d+)\]\s+(.+?)\s+[—-]\s+(https?://\S+)$", user, re.M
        )
        # excerpts keyed by order of appearance; map by index below
        excerpt_list = re.findall(r"^\s*Excerpt:\s*(.+)$", user, re.M)

        lines = [f"# Research report: {topic}", ""]
        if not items:
            lines += [
                "## Summary",
                "",
                "No sources were gathered, so this report cannot make factual claims.",
                "",
                "## Sources",
                "",
                "(none)",
                "",
            ]
            return "\n".join(lines)

        lines += [
            "## Summary",
            "",
            f"This report was compiled by the Scout research agent from {len(items)} "
            f"source(s) on {topic}. Findings below are cited inline.",
            "",
            "## Key findings",
            "",
        ]
        for idx, (num, title, url) in enumerate(items):
            excerpt = excerpt_list[idx] if idx < len(excerpt_list) else title
            excerpt = excerpt.strip()
            if len(excerpt) > 220:
                excerpt = excerpt[:220].rstrip() + "…"
            lines.append(f"- According to [{num}] *{title}*, {excerpt} [{num}].")
        lines += ["", "## Limitations", ""]
        lines.append(
            "This report reflects only the sources listed below, gathered in mock mode "
            "with simulated search results. It is a starting point, not an exhaustive review."
        )
        lines += ["", "## Sources", ""]
        for num, title, url in items:
            lines.append(f"{num}. [{title}]({url})")
        lines.append("")
        return "\n".join(lines)


class GroqLLM(LLMProvider):
    """Groq chat completions via the OpenAI-compatible endpoint.

    The API key comes ONLY from the ``GROQ_API_KEY`` environment variable
    (or an explicit ``api_key`` argument). It is never printed or logged.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 60,
    ) -> None:
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Export it in your shell or put it in a "
                ".env file (see .env.example), or run with --mock."
            )
        self._key = key
        self.model = model or os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> str:
        resp = requests.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {self._key}"},
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
