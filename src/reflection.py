import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from router import ModelRouter

LESSONS_FILE = "config/lessons_learned.json"
MAX_LESSONS = 50
INJECTED_LESSONS = 10

DEFAULT_STATE = {
    "memory_version": 2,
    "lessons": [],
    "total_runs": 0,
    "successful_runs": 0,
    "last_run_at": None,
}


class SelfReflection:
    @staticmethod
    def ensure_storage():
        os.makedirs("config", exist_ok=True)
        if not os.path.exists(LESSONS_FILE):
            with open(LESSONS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_STATE, f, indent=2)
        else:
            # Graceful upgrade of older memory files
            try:
                with open(LESSONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                changed = False
                for k, v in DEFAULT_STATE.items():
                    if k not in data:
                        data[k] = v
                        changed = True
                if changed:
                    with open(LESSONS_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
            except Exception:
                pass

    @classmethod
    def load_memory(cls) -> str:
        cls.ensure_storage()
        try:
            with open(LESSONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            lessons = data.get("lessons", [])
            if not lessons:
                return "No previous lessons recorded."
            return "\n".join([f"- {l}" for l in lessons[-INJECTED_LESSONS:]])
        except Exception:
            return "No previous lessons recorded."

    @classmethod
    def record_execution(cls, prompt: str, result: str, success: bool = True) -> str:
        """Record a run and extract exactly one lesson. Run stats are always
        persisted even if the reflection call itself fails."""
        cls.ensure_storage()
        try:
            with open(LESSONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["total_runs"] = data.get("total_runs", 0) + 1
            if success:
                data["successful_runs"] = data.get("successful_runs", 0) + 1
            data["last_run_at"] = datetime.now(timezone.utc).isoformat()

            lesson = None
            try:
                reflection_prompt = (
                    f"Task Prompt: {prompt}\nExecution Output Snippet: {result[:400]}\n"
                    "Extract ONE concise, objective rule (1 sentence max) about code quality, "
                    "format, or architecture for the agent to remember in future runs. "
                    "Never extract lessons about tool availability, API keys, permissions, or "
                    "external service limitations - those are environment facts, not lessons. "
                    "If the only notable event is a missing credential, output: NO_LESSON"
                )
                lesson = ModelRouter.call_llm(reflection_prompt, task_type="fast")
                clean_lesson = lesson.strip().replace("\n", " ")

                if "NO_LESSON" in clean_lesson.upper():
                    print("[System] Reflection produced no lesson (environment-only event).")
                    lesson = None
                elif clean_lesson and len(clean_lesson) < 200:
                    normalized = clean_lesson.lower()
                    existing = [l.lower() for l in data.get("lessons", [])]
                    if normalized not in existing:
                        data.setdefault("lessons", []).append(clean_lesson)
                        data["lessons"] = data["lessons"][-MAX_LESSONS:]
                    else:
                        print("[System] Memory reflection produced a duplicate lesson. Skipped.")
                else:
                    print("[System] Memory reflection produced an invalid lesson. Skipped.")
            except Exception as e:
                print(f"[Warning] Memory reflection skipped: {e}")

            with open(LESSONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if lesson:
                print(f"[System] Logged new memory state: {lesson.strip()[:120]}")
            return lesson
        except Exception as e:
            print(f"[Warning] Memory state update skipped: {e}")
            return None
