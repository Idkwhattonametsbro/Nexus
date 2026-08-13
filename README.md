# Nexus Autonomous Workspace

An autonomous software architecture system: a browser-based workspace UI (React + Tailwind + Monaco) that you host for free on GitHub Pages, wired to a multi-agent Python backend that runs on GitHub Actions, routes across multiple model providers, remembers what it learns across runs, and commits its own outputs back into the repository.

Strict zinc/slate palette throughout. Indigo glow reserved for active processing states and primary actions. No emoji anywhere in the UI or the Python output streams.

## Repository Structure

```
nexus-workspace/
├── .github/workflows/run_agent.yml   # GitHub Actions pipeline (manual dispatch)
├── workspace/index.html              # The UI workspace (host on GitHub Pages)
├── src/
│   ├── agent.py                      # Orchestrator: memory, research, routing, output
│   ├── router.py                     # Multi-model router (DeepSeek / Groq / OpenRouter)
│   ├── reflection.py                 # Recursive memory: lessons_learned.json
│   └── tools/search.py               # Tavily live research tool
├── config/lessons_learned.json       # Persistent agent memory (committed back after runs)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Execution Flow

1. Pipeline is triggered manually from the Actions tab with a prompt and mode.
2. The agent loads prior memory from `config/lessons_learned.json`.
3. In `full` or `research_only` mode with a Tavily key, it pulls live external context.
4. The router selects the optimal provider for the task type.
5. The response is saved to `output/report_TIMESTAMP.md`; any fenced ```` ```html ```` block is compiled into `output/app_TIMESTAMP.html`.
6. Reflection extracts exactly one lesson from the run and appends it to memory.
7. The workflow commits outputs and the memory file back to the repository (`[skip ci]`).

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
| `DEEPSEEK_API_KEY` | Code / HTML generation (primary) | platform.deepseek.com |
| `OPENROUTER_API_KEY` | General routing fallback | openrouter.ai/keys |
| `GROQ_API_KEY` | Fast tasks (reflection, research) | console.groq.com/keys |
| `TAVILY_API_KEY` | Live web research | app.tavily.com |

4. Run the pipeline: **Actions -> Nexus Autonomous Agent Pipeline -> Run workflow**, enter an architecture directive and mode, then run.

Each run commits `output/` and `config/lessons_learned.json` back to the repo. Note: the action push uses `GITHUB_TOKEN`, so it cannot push to protected branches.

## Host the Workspace UI on GitHub Pages

The workspace is a single self-contained HTML file. No build step required.

**Settings -> Pages -> Source: Deploy from a branch -> branch `main`, folder `/ (root)` -> Save.**

The UI is then live at:

```
https://<YOUR_USERNAME>.github.io/<YOUR_REPO>/workspace/
```

You can also open `workspace/index.html` directly in any browser, or serve it locally with `python -m http.server`.

## Routing Table

| Condition | Provider | Model |
| --- | --- | --- |
| Prompt contains `code` / `html`, or task type is `code` | DeepSeek | `deepseek-chat` |
| Task type is `fast` (reflection) | Groq | `llama-3.3-70b-versatile` |
| Anything else | OpenRouter | `anthropic/claude-3.5-sonnet` |
| No API keys configured | - | `ValueError` visible in run logs |

Only a DeepSeek key is strictly required for code generation tasks. Every other key upgrades the system: Groq accelerates the reflection loop, OpenRouter acts as the general fallback, Tavily enables live research.

## Design Constraints

- Strict zinc/slate palette; indigo glow only on active processing states and primary actions.
- No emoji in the UI or Python output streams.
- Recursive memory: each run adds exactly one lesson; the last 10 lessons are injected into the system prompt of the next run.

## Troubleshooting

- **Run fails with "System Error: No valid API keys found"** - the secrets are missing or misnamed. A DeepSeek key alone is enough for code tasks.
- **Push rejected after a run** - the workflow commits with `GITHUB_TOKEN`; make sure the branch is not protected.
- **Nothing committed after a successful run** - the run produced byte-identical output; no diff means no commit, and the push is a no-op.
- **Monaco editor blank on tab switch** - fixed: the workspace calls `editor.layout()` when the Source Code tab becomes active.
