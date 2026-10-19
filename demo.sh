#!/usr/bin/env bash
# Scout mock-mode demo: full agent loop, no API key, no network LLM calls.
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
"$PY" -m scout "What is retrieval-augmented generation?" \
  --mock --progress \
  -o examples/sample-report-mock.md
echo "---"
echo "Report: examples/sample-report-mock.md"
