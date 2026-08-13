import json
import os
import re
import sys
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from router import ModelRouter
from tools.search import ResearchTool
from reflection import SelfReflection

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
        os.makedirs("output", exist_ok=True)

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
        system_prompt = (
            "You are Nexus, an elite autonomous software architecture system. "
            "Output functional, pristine code blocks without commentary unless requested. "
            f"Adhere strictly to these parameters learned from prior executions:\n{past_memory}"
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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        provider = ModelRouter.last_route.get("provider") if ModelRouter.last_route else "unknown"
        model = ModelRouter.last_route.get("model") if ModelRouter.last_route else "unknown"

        report_path = f"output/report_{timestamp}.md"
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
            blocks = re.findall(pattern, response_text, re.IGNORECASE)
            for i, block in enumerate(blocks):
                if not block or len(block.strip()) < 10:
                    continue
                code_path = f"output/{prefix}_{timestamp}_{i}.{ext}"
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
        }
        manifest_path = f"output/manifest_{timestamp}.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"[System] Run manifest saved to {manifest_path}")

        SelfReflection.record_execution(prompt, response_text, success=True)
        print("[System] Task sequence completed.")

    @staticmethod
    def _extract_artifacts(response_text: str) -> dict:
        found = {}
        for ext, prefix, pattern in ARTIFACT_PATTERNS:
            blocks = re.findall(pattern, response_text, re.IGNORECASE)
            found[ext] = [b for b in blocks if b and len(b.strip()) >= 10]
        return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nexus autonomous agent")
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--mode", type=str, default="full", choices=VALID_MODES)
    args = parser.parse_args()

    agent = NexusAgent()
    agent.process_task(args.prompt, args.mode)
