"""Scout CLI: python -m scout "your topic" [--mock] [--output report.md]"""

from __future__ import annotations

import argparse
import os
import sys

from . import tools
from .agent import ResearchAgent
from .llm import GroqLLM, MockLLM


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (stdlib only). Never overrides real env vars."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="scout",
        description="Agentic research assistant: plans, searches, refines, and "
        "writes a cited markdown report.",
    )
    ap.add_argument("topic", help="Research topic or question, in quotes.")
    ap.add_argument(
        "--mock",
        action="store_true",
        help="Run the full loop with a deterministic fake LLM and simulated "
        "search results. No API key, no network LLM calls.",
    )
    ap.add_argument(
        "--model",
        default=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        help="Groq model for live mode (or set GROQ_MODEL).",
    )
    ap.add_argument(
        "--output", "-o", default=None, help="Write the markdown report to this file."
    )
    ap.add_argument(
        "--max-subquestions", type=int, default=3, help="Planner sub-questions (default: 3)."
    )
    ap.add_argument(
        "--results-per-query", type=int, default=3, help="Pages fetched per query (default: 3)."
    )
    ap.add_argument(
        "--progress", action="store_true", help="Print agent-loop progress to stderr."
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv()

    if args.mock:
        llm = MockLLM()
        search_fn, fetch_fn = tools.mock_search, tools.mock_fetch
    else:
        try:
            llm = GroqLLM(model=args.model)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        search_fn, fetch_fn = tools.web_search, tools.fetch_page

    agent = ResearchAgent(
        llm,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
        max_subquestions=args.max_subquestions,
        results_per_query=args.results_per_query,
        progress=args.progress,
    )
    report = agent.run(args.topic)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"[scout] report written to {args.output}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
