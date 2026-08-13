import os
import re
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from router import ModelRouter
from tools.search import ResearchTool
from reflection import SelfReflection

load_dotenv()


class NexusAgent:
    def __init__(self):
        os.makedirs("output", exist_ok=True)

    def process_task(self, prompt: str, mode: str):
        print(f"[System] Initiating task execution: {prompt}")

        past_memory = SelfReflection.load_memory()

        research_data = ""
        if mode in ["full", "research_only"] and os.getenv("TAVILY_API_KEY"):
            print("[System] Fetching live external context...")
            research_data = ResearchTool.search_web(prompt)

        system_prompt = (
            "You are Nexus, an elite autonomous software architecture system. "
            "Output functional, pristine code blocks without commentary unless requested. "
            f"Adhere strictly to these parameters learned from prior executions:\n{past_memory}"
        )

        full_prompt = prompt
        if research_data:
            full_prompt += f"\n\n[External Context]\n{research_data}"

        print("[System] Routing request to optimal multi-agent swarm...")
        response_text = ModelRouter.call_llm(
            prompt=full_prompt,
            system_prompt=system_prompt,
            task_type="code" if "code" in mode or "html" in prompt.lower() else "general"
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"output/report_{timestamp}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Nexus Execution Report\n\n**Task:** {prompt}\n\n---\n\n{response_text}")
        print(f"[System] Diagnostic report saved to {report_path}")

        html_blocks = re.findall(r"```html\s*([\s\S]*?)```", response_text, re.IGNORECASE)
        if html_blocks:
            code_path = f"output/app_{timestamp}.html"
            with open(code_path, "w", encoding="utf-8") as f:
                f.write(html_blocks[0])
            print(f"[System] Compiled UI component saved to {code_path}")

        SelfReflection.record_execution(prompt, response_text)
        print("[System] Task sequence completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--mode", type=str, default="full")
    args = parser.parse_args()

    agent = NexusAgent()
    agent.process_task(args.prompt, args.mode)
