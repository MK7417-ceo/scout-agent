"""The agentic research loop.

Pipeline (every run, not a single prompt call):

    1. PLAN      — LLM breaks the topic into focused sub-questions.
    2. ACT      — for each sub-question: web_search -> fetch_page (tools).
    3. OBSERVE  — LLM judges whether the results suffice.
    4. REFINE   — if not sufficient, the LLM proposes a refined query and
                  the loop searches/fetches again (at least one refinement
                  pass is attempted per sub-question).
    5. SYNTHESIZE — LLM writes a cited markdown report from the evidence.

The LLM, search and fetch functions are injected, so tests and ``--mock``
mode run the whole loop deterministically with zero network LLM calls.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Callable

PLAN_SYSTEM = (
    "You are the PLANNER of a research agent. Given a research topic, break it "
    "into a short list of focused sub-questions that together cover the topic. "
    'Reply with ONLY a JSON array of strings, e.g. ["q1", "q2", "q3"]. No other text.'
)

OBSERVER_SYSTEM = (
    "You are the OBSERVER of a research agent. Given a sub-question, the search "
    "round number, and the results gathered so far, judge whether the results are "
    "sufficient to answer the sub-question. Reply with ONLY JSON: "
    '{"sufficient": true/false, "refined_query": "<better query or empty string>", '
    '"reason": "<short reason>"}. No other text.'
)

SYNTH_SYSTEM = (
    "You are the SYNTHESIZER of a research agent. Given a topic and numbered "
    "evidence items (each with title, URL and excerpt), write a markdown research "
    "report with: a '# ...' title, '## Summary', '## Key findings' (cite sources "
    "inline as [n]), '## Limitations', and '## Sources' (numbered markdown links). "
    "Every factual claim must carry a citation. Reply with markdown only."
)


def _parse_json_list(text: str) -> list[str]:
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    return [str(x).strip() for x in items if str(x).strip()]


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return {}


class ResearchAgent:
    def __init__(
        self,
        llm,
        search_fn: Callable[..., list[dict]],
        fetch_fn: Callable[..., dict],
        max_subquestions: int = 3,
        results_per_query: int = 3,
        max_refine_rounds: int = 1,
        max_chars_per_page: int = 4000,
        progress: bool = False,
    ) -> None:
        self.llm = llm
        self.search_fn = search_fn
        self.fetch_fn = fetch_fn
        self.max_subquestions = max_subquestions
        self.results_per_query = results_per_query
        self.max_refine_rounds = max_refine_rounds
        self.max_chars_per_page = max_chars_per_page
        self.progress = progress

    def _log(self, message: str) -> None:
        if self.progress:
            print(message, file=sys.stderr)

    # -- public entry point ------------------------------------------------

    def run(self, topic: str) -> str:
        """Run the full plan -> act -> observe -> refine -> synthesize loop."""
        self._log(f"[scout] planning research for: {topic}")
        plan_raw = self.llm.chat(
            [
                {"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": f"TOPIC: {topic}"},
            ]
        )
        sub_questions = _parse_json_list(plan_raw)[: self.max_subquestions] or [topic]
        self._log(f"[scout] plan: {len(sub_questions)} sub-question(s)")

        evidence: list[dict] = []
        seen_urls: set[str] = set()
        for sub_q in sub_questions:
            for item in self._research_subquestion(sub_q):
                if item["url"] and item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    evidence.append(item)

        self._log(f"[scout] synthesizing report from {len(evidence)} source(s)")
        evidence_block = self._format_evidence(topic, evidence)
        report = self.llm.chat(
            [
                {"role": "system", "content": SYNTH_SYSTEM},
                {"role": "user", "content": evidence_block},
            ]
        )
        return report

    # -- loop stages --------------------------------------------------------

    def _research_subquestion(self, sub_question: str) -> list[dict]:
        """Act + observe + refine for one sub-question."""
        collected: list[dict] = []
        query = sub_question
        for round_no in range(self.max_refine_rounds + 1):
            self._log(f"[scout] search round {round_no}: {query}")
            results = self.search_fn(query, self.results_per_query) or []
            for result in results[: self.results_per_query]:
                url = result.get("url", "")
                if not url:
                    continue
                page = self.fetch_fn(url, self.max_chars_per_page)
                collected.append(
                    {
                        "sub_question": sub_question,
                        "query": query,
                        "url": url,
                        "title": page.get("title") or result.get("title", ""),
                        "snippet": result.get("snippet", ""),
                        "text": (page.get("text", "") or "")[:1200],
                    }
                )
            observation = self._observe(sub_question, round_no, results)
            if observation.get("sufficient") or round_no == self.max_refine_rounds:
                break
            refined = (observation.get("refined_query") or "").strip()
            if refined:
                self._log(f"[scout] refining query -> {refined}")
                query = refined
            else:
                break
        return collected

    def _observe(self, sub_question: str, round_no: int, results: list[dict]) -> dict:
        brief = "\n".join(
            f"- {r.get('title', '')} ({r.get('url', '')})" for r in results[:5]
        ) or "(no results)"
        raw = self.llm.chat(
            [
                {"role": "system", "content": OBSERVER_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"SUB-QUESTION: {sub_question}\n"
                        f"ROUND: {round_no}\n"
                        f"RESULTS:\n{brief}"
                    ),
                },
            ]
        )
        observation = _parse_json_object(raw)
        if not isinstance(observation, dict):
            observation = {}
        observation.setdefault("sufficient", True)
        return observation

    @staticmethod
    def _format_evidence(topic: str, evidence: list[dict]) -> str:
        lines = [f"TOPIC: {topic}", "EVIDENCE:"]
        for i, item in enumerate(evidence, 1):
            lines.append(f"[{i}] {item['title']} — {item['url']}")
            excerpt = " ".join((item["text"] or item["snippet"] or "").split())
            lines.append(f"    Excerpt: {excerpt[:400]}")
        return "\n".join(lines)
