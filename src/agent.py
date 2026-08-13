import json
import os
import re
import sys
import shutil
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from router import ModelRouter
from tools.search import ResearchTool
from reflection import SelfReflection
from repo_tool import GitHubRepoTool

load_dotenv()

ARTIFACT_PATTERNS = [
    ("html", "app", r"```html\s*([\s\S]*?)```"),
    ("css", "style", r"```css\s*([\s\S]*?)```"),
    ("js", "script", r"```(?:javascript|js)\s*([\s\S]*?)```"),
    ("python", "module", r"```python\s*([\s\S]*?)```"),
]

VALID_MODES = ("full", "code", "research_only", "fast")


def run_context() -> str:
    """Inject CI metadata so the model knows where it is executing."""
    repo = os.getenv("GITHUB_REPOSITORY", "")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    sha = os.getenv("GITHUB_SHA", "")
    actor = os.getenv("GITHUB_ACTOR", "")
    parts = []
    if repo:
        parts.append(f"repository: {repo}")
    if run_id:
        parts.append(f"run: {run_id}")
    if sha:
        parts.append(f"commit: {sha[:8]}")
    if actor:
        parts.append(f"actor: {actor}")
    return "\n".join(parts) if parts else ""


class NexusAgent:
    def __init__(self):
        self.output_dir = os.getenv("OUTPUT_DIR", "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def process_task(self, prompt: str, mode: str):
        print(f"[System] Initiating task execution: {prompt}")
        started = datetime.now(timezone.utc)

        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Valid modes: {', '.join(VALID_MODES)}")

        past_memory = SelfReflection.load_memory()

        research_data = ""
        if mode in ("full", "research_only") and os.getenv("TAVILY_API_KEY"):
            print("[System] Fetching live external context...")
            research_data = ResearchTool.search_web(prompt)

        context = run_context()
        complex_task = any(s in prompt.lower() for s in ("repo", "repository", "project", "architecture", "plan"))
        system_prompt = (
            "You are Nexus, an elite autonomous software architecture system. "
            "Output functional, pristine code blocks without commentary unless requested. "
            f"Adhere strictly to these parameters learned from prior executions:\n{past_memory}"
        )
        if complex_task:
            system_prompt += (
                "\n\nThis is a complex multi-step directive. Begin your response with a concise "
                "'## Plan' section listing the architecture steps, then state any key assumptions, "
                "then deliver the complete artifacts in fenced code blocks. Never claim an action "
                "you did not perform."
            )
        if context:
            system_prompt += f"\n\n[Execution Context]\n{context}"

        full_prompt = prompt
        if research_data:
            full_prompt += f"\n\n[External Context]\n{research_data}"

        task_type = "code" if mode == "code" or "html" in prompt.lower() else "general"
        if mode == "fast":
            task_type = "fast"

        print(f"[System] Routing request to optimal multi-agent swarm (task type: {task_type})...")
        response_text = ModelRouter.call_llm(
            prompt=full_prompt,
            system_prompt=system_prompt,
            task_type=task_type,
        )

        # Self-healing pass: if a code task produced no HTML artifact, retry once
        # with a strict single-block directive.
        artifacts = self._extract_artifacts(response_text)
        if task_type == "code" and not artifacts.get("html") and mode in ("full", "code"):
            print("[System] No HTML artifact detected. Issuing self-healing retry with strict format...")
            response_text = ModelRouter.call_llm(
                prompt=prompt + "\n\nIMPORTANT: Respond with a single fenced ```html code block containing ONLY the complete HTML document. No explanations, no markdown outside the fence.",
                system_prompt=system_prompt,
                task_type="code",
            )
            artifacts = self._extract_artifacts(response_text)

        # Quality review pass: a second model critiques and polishes generated
        # HTML before it is committed. Best-effort; never fails the run.
        review = {"enabled": False, "applied": False}
        if task_type == "code" and artifacts.get("html") and os.getenv("NEXUS_REVIEW", "1") != "0":
            review["enabled"] = True
            try:
                improved = self._review_artifact(prompt, artifacts["html"][0])
                if improved:
                    artifacts["html"][0] = improved
                    review["applied"] = True
                    print("[System] Review pass applied an improved artifact.")
                else:
                    print("[System] Review pass approved the artifact as-is.")
            except Exception as e:
                print(f"[Warning] Review pass skipped: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        provider = ModelRouter.last_route.get("provider") if ModelRouter.last_route else "unknown"
        model = ModelRouter.last_route.get("model") if ModelRouter.last_route else "unknown"

        report_path = f"{self.output_dir}/report_{timestamp}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Nexus Execution Report\n\n")
            f.write(f"**Task:** {prompt}\n\n")
            f.write(f"**Mode:** {mode}  \n")
            f.write(f"**Provider:** {provider} ({model})  \n")
            f.write(f"**Latency:** {elapsed_ms}ms  \n")
            f.write(f"**Run ID:** {os.getenv('GITHUB_RUN_ID', 'local')}  \n\n")
            f.write(f"---\n\n{response_text}")
        print(f"[System] Diagnostic report saved to {report_path}")

        written = []
        for ext, prefix, pattern in ARTIFACT_PATTERNS:
            for i, block in enumerate(artifacts.get(ext, [])):
                if not block or len(block.strip()) < 10:
                    continue
                code_path = f"{self.output_dir}/{prefix}_{timestamp}_{i}.{ext}"
                with open(code_path, "w", encoding="utf-8") as f:
                    f.write(block.strip() + "\n")
                written.append(code_path)
                print(f"[System] Compiled {ext.upper()} artifact saved to {code_path}")

        if task_type == "code" and not written:
            print("[Warning] No compilable artifacts found in the model response.")

        manifest = {
            "timestamp": timestamp,
            "run_id": os.getenv("GITHUB_RUN_ID", "local"),
            "prompt": prompt,
            "mode": mode,
            "provider": provider,
            "model": model,
            "latency_ms": elapsed_ms,
            "artifacts": written,
            "research": bool(research_data),
            "review": review,
        }

        # Repo creation: if the directive asks for a repository, seed a new
        # GitHub repo from the generated artifacts (requires NEXUS_GITHUB_TOKEN).
        repo_result = None
        repo_intent = any(s in prompt.lower() for s in ("create a github repo", "create a github repository", "push the repository", "new github repository", "create the repository"))
        if repo_intent:
            print("[System] Repo creation requested. Checking GitHub tooling...")
            files = {}
            for w in written:
                rel = os.path.basename(w)
                with open(w, "r", encoding="utf-8") as f:
                    files[f"generated/{rel}"] = f.read()
            with open(report_path, "r", encoding="utf-8") as f:
                files["REPORT.md"] = f.read()
            files["README.md"] = f"# {prompt[:60]}\n\nGenerated autonomously by the Nexus agent.\n\nSee the full report: `REPORT.md`"
            repo_name = "nexus-" + timestamp
            repo_result = GitHubRepoTool.create_repo(name=repo_name, description=prompt[:120], private=False, files=files)
            print(repo_result["message"])
            manifest["repo_creation"] = repo_result
        else:
            manifest["repo_creation"] = None

        manifest_path = f"{self.output_dir}/manifest_{timestamp}.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"[System] Run manifest saved to {manifest_path}")

        # Pointer files consumed by the GitHub Pages control surface.
        with open(f"{self.output_dir}/latest_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        shutil.copy(report_path, f"{self.output_dir}/latest_report.md")
        html_artifacts = [w for w in written if w.endswith(".html")]
        if html_artifacts:
            shutil.copy(html_artifacts[0], f"{self.output_dir}/latest_app.html")
            print(f"[System] Live preview pointer updated ({self.output_dir}/latest_app.html)")

        SelfReflection.record_execution(prompt, response_text, success=True)
        print("[System] Task sequence completed.")

    @staticmethod
    def _extract_artifacts(response_text: str) -> dict:
        found = {}
        for ext, prefix, pattern in ARTIFACT_PATTERNS:
            blocks = re.findall(pattern, response_text, re.IGNORECASE)
            found[ext] = [b for b in blocks if b and len(b.strip()) >= 10]
        return found

    @staticmethod
    def _review_artifact(prompt: str, artifact: str) -> str:
        """Critique the artifact against the directive. Returns an improved
        standalone HTML document, or None if the artifact is approved as-is."""
        review_prompt = (
            f"Original directive: {prompt}\n\n"
            f"Generated artifact:\n{artifact[:6000]}\n\n"
            "You are a senior design engineer. Critique the artifact against the directive. "
            "Return ONLY ONE of:\n"
            "1. A single fenced ```html block with the complete improved version. "
            "Fix layout defects, polish the visual hierarchy, and ensure it is a functional "
            "standalone page. Keep the same stack (inline CSS, no external dependencies).\n"
            "2. The exact token NO_CHANGE if the artifact already fully satisfies the directive."
        )
        out = ModelRouter.call_llm(
            prompt=review_prompt,
            system_prompt="You are Nexus Review, a senior design engineer enforcing premium visual standards.",
            task_type="fast",
        ).strip()
        if "NO_CHANGE" in out.upper() and "```" not in out:
            return None
        blocks = re.findall(r"```html\s*([\s\S]*?)```", out, re.IGNORECASE)
        if blocks and len(blocks[0].strip()) >= 10 and blocks[0].strip() != artifact.strip():
            return blocks[0].strip()
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nexus autonomous agent")
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--mode", type=str, default="full", choices=VALID_MODES)
    args = parser.parse_args()

    agent = NexusAgent()
    agent.process_task(args.prompt, args.mode)
