# Nexus Autonomous Workspace

An autonomous software architecture system: a browser-based control surface (React + Tailwind + Monaco) hosted free on GitHub Pages, wired to a resilient multi-agent Python backend that runs on GitHub Actions, routes across multiple model providers with automatic fallback, remembers what it learns across runs, self-heals failed generations, and commits its own outputs back into the repository.

Strict zinc/slate palette throughout. Indigo glow reserved for active processing states and primary actions. No emoji anywhere in the UI or the Python output streams.

## Repository Structure

```
nexus-workspace/
├── .github/workflows/
│   ├── run_agent.yml              # Autonomous pipeline (manual dispatch, commits outputs back)
│   └── ci.yml                     # Smoke tests on every push to src/
├── workspace/index.html           # The 5-zone control surface (host on GitHub Pages)
├── src/
│   ├── agent.py                   # Orchestrator: memory, research, routing, self-healing, artifacts
│   ├── router.py                  # Resilient multi-provider router with fallback chains + retries
│   ├── reflection.py              # Recursive memory (dedupe, cap, versioned lessons_learned.json)
│   └── tools/search.py            # Tavily live research tool
├── tests/test_smoke.py            # 14 smoke tests (routing, fallback, retries, memory, agent flow)
├── config/lessons_learned.json    # Persistent agent memory (committed back after each run)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Execution Flow

1. Pipeline is triggered manually from the Actions tab with a prompt and mode.
2. The agent loads the last 10 lessons from `config/lessons_learned.json`.
3. In `full` or `research_only` mode with a Tavily key, it pulls live external context.
4. The router resolves a provider chain for the task type and calls the best available model.
5. Outputs are written to `output/`:
   - `report_TIMESTAMP.md` - full diagnostic report
   - `app/style/script/module_TIMESTAMP_N.ext` - compiled artifacts extracted from fenced code blocks
   - `manifest_TIMESTAMP.json` - run metadata (provider, model, latency, artifacts)
6. If a code task produced no HTML artifact, the agent retries once with a strict single-block directive (self-healing).
7. Reflection extracts exactly one lesson per run (deduplicated, capped at 50) and updates memory.
8. The workflow commits `output/` and the memory file back to the repository (`[skip ci]`).

## Routing and Self-Healing

| Task type | Primary provider | Fallback chain |
| --- | --- | --- |
| `code` | DeepSeek (`deepseek-chat`) | OpenRouter (Claude 3.5 Sonnet) -> OpenAI (gpt-4o-mini) -> Groq |
| `fast` (reflection) | Groq (llama-3.3-70b) | DeepSeek -> OpenRouter -> OpenAI |
| `general` | OpenRouter (Claude 3.5 Sonnet) | OpenAI -> DeepSeek -> Groq |

- Every provider is attempted up to 3 times with exponential backoff on 429 / 5xx / network errors.
- If the primary provider fails, the next configured provider takes over automatically.
- Only `DEEPSEEK_API_KEY` is strictly required for code generation; every other key adds resilience.
- If every provider fails, the run fails loudly with a summary of all errors.

## Local Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in your keys
python src/agent.py --prompt "Build a dark-mode operations dashboard" --mode full
```

Local output lands in `output/`. The agent reads `.env` automatically.

## Deploy to GitHub

1. Create an empty repository on GitHub (no README, no .gitignore).

2. Push this folder as the repository root:

```bash
cd nexus-workspace
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
git push -u origin main
```

3. Add repository secrets: **Settings -> Secrets and variables -> Actions -> New repository secret**

| Secret | Used for | Get it at |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | Code generation (primary) | platform.deepseek.com |
| `OPENROUTER_API_KEY` | General routing fallback | openrouter.ai/keys |
| `GROQ_API_KEY` | Fast tasks (reflection) | console.groq.com/keys |
| `OPENAI_API_KEY` | Extra fallback route | platform.openai.com |
| `TAVILY_API_KEY` | Live web research | app.tavily.com |

4. Run the pipeline: **Actions -> Nexus Autonomous Agent Pipeline -> Run workflow**, enter an architecture directive and mode, then run.

Each run commits `output/` and `config/lessons_learned.json` back to the repo, and uploads the same artifacts to the run page for download. Note: the action push uses `GITHUB_TOKEN`, so it cannot push to protected branches. Concurrent runs are serialized by a concurrency group.

## Host the Control Surface on GitHub Pages

The workspace is a single self-contained HTML file. No build step required.

**Settings -> Pages -> Source: Deploy from a branch -> branch `main`, folder `/ (root)` -> Save.**

The UI is then live at:

```
https://<YOUR_USERNAME>.github.io/<YOUR_REPO>/workspace/
```

Five zones: **Command Stream** (directive chat + live thought stream), **Preview Canvas**, **Source Code** (Monaco with a strict zinc/indigo theme), **Agent Memory** (live view of `lessons_learned.json`), and **System Logs**. The **DEPLOY TO PIPELINE** button deep-links to the Actions workflow automatically.

Generated apps committed by the pipeline are also viewable on Pages, e.g. `https://<YOUR_USERNAME>.github.io/<YOUR_REPO>/output/app_20260101_120000_0.html`.

## Smoke Tests

Run locally:

```bash
python -m unittest discover -s tests -v
```

The CI workflow runs the same suite on every push touching `src/`.

## Design Constraints

- Strict zinc/slate palette; indigo glow only on active processing states and primary actions.
- No emoji in the UI or Python output streams.
- Recursive memory: each run adds exactly one lesson (deduplicated); the last 10 lessons are injected into the system prompt of the next run.

## Troubleshooting

- **Run fails with "System Error: No valid API keys found"** - the secrets are missing or misnamed. A DeepSeek key alone is enough for code tasks.
- **Run fails with "All providers exhausted"** - every configured provider errored; the message lists each failure. Check key validity and rate limits.
- **Push rejected after a run** - the workflow commits with `GITHUB_TOKEN`; make sure the branch is not protected.
- **Nothing committed after a successful run** - the run produced byte-identical output; no diff means no commit, and the push is a no-op.
- **Monaco editor blank on tab switch** - fixed: the workspace calls `editor.layout()` when the Source Code tab becomes active.
