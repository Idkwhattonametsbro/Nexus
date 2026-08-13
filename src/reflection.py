import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from router import ModelRouter

LESSONS_FILE = "config/lessons_learned.json"


class SelfReflection:
    @staticmethod
    def ensure_storage():
        os.makedirs("config", exist_ok=True)
        if not os.path.exists(LESSONS_FILE):
            with open(LESSONS_FILE, "w", encoding="utf-8") as f:
                json.dump({"lessons": [], "total_runs": 0, "successful_runs": 0}, f, indent=2)

    @classmethod
    def load_memory(cls) -> str:
        cls.ensure_storage()
        try:
            with open(LESSONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            lessons = data.get("lessons", [])
            if not lessons:
                return "No previous lessons recorded."
            return "\n".join([f"- {l}" for l in lessons[-10:]])
        except Exception:
            return "No previous lessons recorded."

    @classmethod
    def record_execution(cls, prompt: str, result: str):
        cls.ensure_storage()
        try:
            with open(LESSONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["total_runs"] = data.get("total_runs", 0) + 1
            data["successful_runs"] = data.get("successful_runs", 0) + 1

            reflection_prompt = (
                f"Task Prompt: {prompt}\nExecution Output Snippet: {result[:400]}\n"
                "Extract ONE concise, objective rule (1 sentence max) for the agent to remember in future runs."
            )
            lesson = ModelRouter.call_llm(reflection_prompt, task_type="fast")
            clean_lesson = lesson.strip().replace("\n", " ")

            if clean_lesson and len(clean_lesson) < 200:
                data["lessons"].append(clean_lesson)

            with open(LESSONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"[System] Logged new memory state: {clean_lesson}")
        except Exception as e:
            print(f"[Warning] Memory reflection skipped: {e}")
