# Scout — an agentic research assistant (CLI)

Scout takes a topic, **plans** sub-questions, **searches the web and fetches pages
with tools**, **observes** the results, **refines** its queries when results are thin,
and **synthesizes** a cited markdown report. It is a genuine agent loop — not a
single prompt call.

Built with Python, zero paid services. Web search goes through DuckDuckGo (free,
no key). The LLM is pluggable: a deterministic **mock provider** for offline
use/tests, or **Groq's free tier** via its OpenAI-compatible endpoint.

## How the agent loop works

```
topic
  │
  ▼
┌──────────┐
│ PLANNER  │  LLM breaks the topic into sub-questions (JSON)
└────┬─────┘
     ▼
┌──────────┐     ┌────────────┐     ┌────────────┐
│  SEARCH  │────▶│ FETCH PAGE │────▶│  OBSERVER  │  LLM judges: sufficient?
│ (DuckDuckGo) │     │ (requests) │     │            │  no → refined query ↺
└──────────┘     └────────────┘     └─────┬──────┘
                                         │ yes
                                         ▼
                                  ┌─────────────┐
                                  │ SYNTHESIZER │  LLM writes cited markdown
                                  └─────────────┘
```

Every run performs: 1 planning call, N×(search+fetch) tool rounds, at least one
observe/refine iteration per sub-question, and 1 synthesis call. Evidence is
deduplicated by URL before synthesis, and every factual claim in the report is
expected to carry an inline `[n]` citation with a Sources section.

## Quickstart

```bash
cd scout-agent
pip install -r requirements.txt

# Mock mode — full loop, zero keys, zero network LLM calls:
python -m scout "What is retrieval-augmented generation?" --mock

# Save the report:
python -m scout "What is retrieval-augmented generation?" --mock -o report.md

# Watch the loop think (progress goes to stderr, report stays clean on stdout):
python -m scout "What is retrieval-augmented generation?" --mock --progress
```

## Live mode (Groq, free tier)

1. Get a free key at https://console.groq.com/keys
2. `cp .env.example .env` and put the key in `GROQ_API_KEY=` — or `export GROQ_API_KEY=...`
3. Run without `--mock`:

```bash
python -m scout "What is retrieval-augmented generation?" --progress
```

The key is read **only** from the environment. It is never hardcoded, never logged,
and `.env` is git-ignored. To use a different model: `--model <name>` or `GROQ_MODEL`.

## Tests

```bash
pytest -q
```

All tests run offline (the mock provider + fixture HTML; live tools are only
exercised through failure-path tests with stubbed networking).

## Project structure

```
scout-agent/
├── scout/
│   ├── __init__.py
│   ├── __main__.py      # python -m scout
│   ├── cli.py           # argparse, --mock / --output / --progress
│   ├── agent.py         # the plan → act → observe → refine → synthesize loop
│   ├── llm.py           # provider abstraction: MockLLM, GroqLLM
│   └── tools.py         # web_search (DuckDuckGo), fetch_page, mock tools
├── tests/               # pytest, all runnable offline
├── examples/
│   └── sample-report-mock.md   # real output of the mock demo
├── demo.sh              # runs the mock demo end-to-end
├── DEMO.md              # what the demo does and shows
├── requirements.txt     # requests, pytest — nothing else
├── .env.example         # placeholder only, no secrets
└── LICENSE              # MIT
```

## Honest limitations

- **Mock mode uses simulated search results** (three canned RAG pages). The loop is
  real, but the "sources" are illustrative — see `DEMO.md`. Run live mode for real
  research.
- DuckDuckGo's HTML endpoint is scraped, not an official API — it can break or
  rate-limit. Failures are reported inline, never raised.
- Page fetching is naive text extraction: no JavaScript rendering, no PDFs.
- The mock LLM's synthesis is templated from the evidence — coherent, not creative.
- Groq's free tier has rate limits; large topics may need smaller
  `--max-subquestions` / `--results-per-query`.
- Reports are a starting point for research, not a substitute for reading sources.
