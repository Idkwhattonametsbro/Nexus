# Nexus Autonomous Workspace

An autonomous software architecture system: a light, premium, phone-friendly control surface (React + Tailwind + Monaco) hosted free on GitHub Pages, wired to a resilient multi-agent Python backend that runs on GitHub Actions, routes across multiple current-generation model providers with automatic fallback, remembers what it learns across runs, reviews and polishes its own output, self-heals failed generations, and commits its own work back into the repository.

Design language: creamy white, soft warm borders, premium orange accents. Fully responsive (phone + desktop). No emoji anywhere in the UI or the Python output streams.

## Repository Structure

```
nexus-workspace/
├── .github/workflows/
│   ├── run_agent.yml              # Autonomous pipeline (manual dispatch, commits outputs back)
│   └── ci.yml                     # Smoke tests on every push to src/
├── workspace/index.html           # The 5-zone control surface (host on GitHub Pages)
├── src/
│   ├── agent.py                   # Orchestrator: memory, research, routing, review, self-healing, artifacts
│   ├── router.py                  # Resilient multi-provider router with fallback chains + retries
│   ├── reflection.py              # Recursive memory (dedupe, cap, versioned lessons_learned.json)
│   └── tools/search.py            # Tavily live research tool
├── tests/test_smoke.py            # 18 smoke tests (routing, fallback, retries, review, memory, agent flow)
├── output/                        # Run artifacts + live-preview pointers (committed after each run)
│   ├── latest_app.html            # Latest generated app (rendered live in the Preview Canvas)
│   ├── latest_manifest.json       # Latest run metadata (provider, model, latency, artifacts)
│   └── latest_report.md           # Latest diagnostic report
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
   - `manifest_TIMESTAMP.json` - run metadata (provider, model, latency, artifacts, review status)
6. If a code task produced no HTML artifact, the agent retries once with a strict single-block directive (self-healing).
7. **Review pass**: a second model (fast chain) critiques the generated HTML against the directive and returns either an improved version or `NO_CHANGE`. Improvements are applied before commit; disabled with `NEXUS_REVIEW=0`.
8. Reflection extracts exactly one lesson per run (deduplicated, capped at 50) and updates memory.
9. The workflow commits `output/` and the memory file back to the repository (`[skip ci]`), and uploads the same artifacts to the run page.

## Routing and Self-Healing

Current-generation models, verified August 2026:

| Task type | Primary provider | Fallback chain |
| --- | --- | --- |
| `code` | DeepSeek (`deepseek-v4-pro`) | OpenRouter (Claude Sonnet 4.6) -> OpenAI (gpt-4o-mini) -> Groq (GPT-OSS-120B) |
| `fast` (reflection/review) | Groq (`openai/gpt-oss-120b`) | DeepSeek -> OpenRouter -> OpenAI |
| `general` | OpenRouter (`anthropic/claude-sonnet-4.6`) | OpenAI -> DeepSeek -> Groq |

- The OpenRouter key gives access to Claude Sonnet 4.6 - the current agentic-coding flagship.
- Every provider is attempted up to 3 times with exponential backoff on 429 / 5xx / network errors.
- If the primary provider fails, the next configured provider takes over automatically.
- Override any model via env: `NEXUS_MODEL_DEEPSEEK`, `NEXUS_MODEL_GROQ`, `NEXUS_MODEL_OPENROUTER`, `NEXUS_MODEL_OPENAI`.
- Note: DeepSeek's legacy `deepseek-chat` name was discontinued on 2026-07-24; the v4 line (`deepseek-v4-pro` / `deepseek-v4-flash`) is current.
- Only `DEEPSEEK_API_KEY` is strictly required for code generation; every other key adds resilience and quality.

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
| `OPENROUTER_API_KEY` | Claude-level general routing | openrouter.ai/keys |
| `GROQ_API_KEY` | Fast tasks (reflection + review) | console.groq.com/keys |
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

**Live preview**: the Preview Canvas renders `output/latest_app.html` in a sandboxed iframe with a run-info header (provider, model, latency, artifacts, review status). A seed dashboard ships in the repo; the first real pipeline run replaces it automatically. Generated apps are also directly viewable on Pages, e.g. `https://<YOUR_USERNAME>.github.io/<YOUR_REPO>/output/app_20260101_120000_0.html`.

## Benchmark Results (August 2026)

Five benchmark tasks across categories and difficulty levels were run against
the live pipeline (Groq GPT-OSS-120B, zero-cost mode):

| Task | Category | Difficulty | Result | Notes |
| --- | --- | --- | --- | --- |
| Portfolio landing page | Static HTML | Easy | PASS | Hero/about/contact, responsive, orange accents, review applied |
| To-do app | Interactive JS | Medium | PASS | Add/complete/delete, filters, localStorage, counter, review applied |
| Kanban board | Complex app | Hard | PASS | Drag-drop, columns, labels, localStorage, stats, review applied |
| Create a GitHub repo (SaaS starter) | Meta / agentic | Hard | PASS* | Produced Plan + Key Assumptions + full file manifest; correctly reported missing NEXUS_GITHUB_TOKEN instead of failing silently |
| Multi-agent architecture analysis | Reasoning | Medium | PASS | Structured markdown, 20 headings, Plan + Assumptions sections |

*Repo creation: with `NEXUS_GITHUB_TOKEN` configured, the agent creates and
seeds the repo via the GitHub API (`src/repo_tool.py`). Without it, it states
the requirement explicitly in the run manifest.

**Findings fixed after the benchmark:**
- Reflection could learn counterproductive lessons from environment limits
  (e.g. "never push repos" when a token was missing) - reflection now ignores
  tool-availability events (`NO_LESSON` guard).
- Multi-file repo tasks only extracted a few fenced blocks as artifacts - repo
  seeding now includes the full report and every generated artifact.
- Code detection now covers frontend/backend/api/database/docker/repository
  prompts, so those routes get the code chain and review pass.

## Smoke Tests

Run locally:

```bash
python -m unittest discover -s tests -v
```

The CI workflow runs the same suite on every push touching `src/`.

## Zero-Cost Mode

No paid API credit required. The router falls back automatically:

- **Groq (free tier)** - carries code generation, reflection, and review.
- **Tavily (free tier)** - carries live research.
- DeepSeek / OpenRouter / OpenAI keys are optional upgrades; when their accounts
  have no credit, the router now fails them fast (non-retryable 402) and lands on
  Groq within seconds instead of burning retry backoff.
- Free-tier rate limits are handled by per-provider retry with backoff and the
  workflow concurrency guard.

## Chat-Native Agent (V6)

The workspace is a **conversational agent**. The chat is the product; GitHub is
background plumbing that holds the secrets.

- **Background brain (default)**: Nexus thinks through the GitHub Actions
  pipeline using your repository secrets - API keys never enter the chat or
  the browser. You only paste a GitHub token once (PIPELINE modal, Actions
  read/write) so the chat can dispatch runs. Results stream back into the
  chat with the pipeline's own reasoning trace.
- **Fast brain (optional)**: add an LLM key in BRAIN for instant in-browser
  replies (Groq / OpenRouter / DeepSeek), stored in localStorage only.
- **Conversational**: greetings and questions get real replies; ambiguous
  build requests trigger clarifying questions with tap-to-answer options.
- **Reasoning transparency**: every turn shows a "Thought for Xs" pill that
  expands into the full reasoning trace (real pipeline log lines in background
  mode).
- **Build loop**: generate -> review (second model critiques) -> fix -> iterate
  (up to 3 rounds) -> deliver. Every artifact is a file card with syntax
  highlighting, iteration count, inline PREVIEW, DOWNLOAD, and optional
  SAVE to the GitHub repo (background).
- **Session memory**: a lesson is extracted after each approved build and
  injected into future prompts (localStorage, capped at 10).
- **Export**: the whole session exports as a downloadable markdown file.

Zero browser keys required: the chat dispatches `chat`-mode pipeline runs that
use the secrets you already configured in GitHub.

## Design Constraints

- Light premium palette: creamy white background, white cards, soft warm borders,
  and a single orange accent reserved for active processing states and primary
  actions. No emoji anywhere in the UI or the Python output streams.
- Fully responsive: the control surface adapts to phones (stacked layout with a
  bottom directive dock and slide-up thought stream) and desktops (sidebar
  layout with status bar).
- Recursive memory: each run adds exactly one lesson (deduplicated); the last 10
  lessons are injected into the system prompt of the next run.
- Review pass: generated HTML is critiqued by a second model before it is committed.

## Troubleshooting

- **Run fails with "System Error: No valid API keys found"** - the secrets are missing or misnamed. A DeepSeek key alone is enough for code tasks.
- **Run fails with "All providers exhausted"** - every configured provider errored; the message lists each failure. Check key validity and rate limits.
- **Run fails with a 400 model-not-found** - the provider renamed a model; set `NEXUS_MODEL_<PROVIDER>` to the current ID (DeepSeek legacy names were discontinued 2026-07-24).
- **Push rejected after a run** - the workflow commits with `GITHUB_TOKEN`; make sure the branch is not protected.
- **Nothing committed after a successful run** - the run produced byte-identical output; no diff means no commit, and the push is a no-op.
- **Monaco editor blank on tab switch** - fixed: the workspace calls `editor.layout()` when the Source Code tab becomes active.
