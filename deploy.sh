#!/usr/bin/env bash
# Scout deploy script: test -> secret scan -> git init -> commit -> push to GitHub.
#
# Usage:
#   ./deploy.sh                                    # pushes to MK7417-ceo/scout-agent
#   ./deploy.sh https://github.com/USER/REPO.git   # custom repo URL
#
# Run this where git has GitHub auth (e.g. a Codespace with `gh auth login`).
# Create the EMPTY repo on GitHub first (do not add README/license there).

set -euo pipefail
cd "$(dirname "$0")"

REPO_URL="${1:-https://github.com/MK7417-ceo/scout-agent.git}"
GIT_USER_NAME="${GIT_USER_NAME:-MK7417-ceo}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-workwithmohit26@gmail.com}"

echo "== 1/4 tests =="
if python3 -c "import pytest" 2>/dev/null; then
  python3 -m pytest -q || { echo "ERROR: tests failed — fix before deploying."; exit 1; }
  echo "tests green"
else
  echo "WARNING: pytest not installed; skipping test gate."
  echo "         run: pip install -r requirements.txt && ./deploy.sh"
fi

echo "== 2/4 secret scan =="
if grep -rniE "gsk_[A-Za-z0-9_-]{20,}|sk-(live|test)-[A-Za-z0-9]{10,}|xox[bap]-" \
    --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.pytest_cache \
    --exclude="deploy.sh" . ; then
  echo "ERROR: possible secret detected above — remove it before deploying."
  exit 1
fi
echo "no secrets found"

echo "== 3/4 git commit =="
[ -d .git ] || git init -b main
git add -A
git -c user.name="$GIT_USER_NAME" -c user.email="$GIT_USER_EMAIL" commit -m \
"feat(scout): agentic research assistant

Plans sub-questions, searches/fetches with free tools, refines queries when
results are thin, synthesizes cited markdown reports. Deterministic mock mode
(offline, zero keys) plus Groq free-tier live mode. 20/20 pytest green." \
  || echo "(nothing new to commit)"
git branch -M main

echo "== 4/4 push =="
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git push -u origin main

echo ""
echo "deployed: $REPO_URL"
