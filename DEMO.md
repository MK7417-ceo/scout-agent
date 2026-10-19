# Scout demo

The demo runs the **entire agent loop in mock mode**: no API key, no network
calls to any LLM. It exercises every stage so you can see the agent think.

## Run it

```bash
cd scout-agent
pip install -r requirements.txt
./demo.sh
# or directly:
python -m scout "What is retrieval-augmented generation?" --mock --progress \
  -o examples/sample-report-mock.md
```

## What you should see

With `--progress`, stderr shows the loop working:

```
[scout] planning research for: What is retrieval-augmented generation?
[scout] plan: 3 sub-question(s)
[scout] search round 0: What is What is retrieval-augmented generation??
[scout] refining query -> ... overview explained
[scout] search round 1: ...
[scout] synthesizing report from 3 source(s)
[scout] report written to examples/sample-report-mock.md
```

(Yes — the mock planner's templated sub-questions read a little awkwardly, e.g.
"What is What is ...?". That is a cosmetic artifact of the *deterministic fake*
used for offline testing, not of the agent design; with a real LLM in live mode
the planner writes natural sub-questions.)

The report itself (`examples/sample-report-mock.md`) contains:

- `# Research report: ...` title
- `## Summary`, `## Key findings` (with inline `[1]`, `[2]`, `[3]` citations),
  `## Limitations`, and `## Sources` (numbered markdown links)

## Honesty note

Mock mode uses **simulated search results** (three canned pages about RAG, with
real public URLs as labels). The *loop* — plan, tool calls, observation,
refinement, synthesis — is genuinely executed; the *content* of the sources is
illustrative so the demo works offline and reproducibly. For real research on
live web content, run with a free Groq key (see README).
