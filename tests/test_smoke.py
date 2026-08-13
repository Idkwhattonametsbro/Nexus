import os
import sys
import json
import time
import glob
import shutil
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, SRC_DIR)

# NOTE: importing as top-level modules (router, agent, reflection) keeps a single
# module identity shared with the internal `from router import ...` imports.
import router
import reflection
import agent as agent_module
from tools.search import ResearchTool
from reflection import SelfReflection
from agent import NexusAgent


def clear_env():
    for k in ("DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY"):
        os.environ.pop(k, None)


class TestRouting(unittest.TestCase):
    def setUp(self):
        clear_env()

    def test_no_keys_raises_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            router.ModelRouter.route_request("build a dashboard")
        self.assertIn("No valid API keys", str(ctx.exception))

    def test_code_routes_to_deepseek(self):
        os.environ["DEEPSEEK_API_KEY"] = "dsk-fake"
        os.environ["GROQ_API_KEY"] = "groq-fake"
        r = router.ModelRouter.route_request("write html for a dashboard", "general")
        self.assertEqual(r["provider"], "DeepSeek")
        self.assertEqual(r["model"], "deepseek-v4-pro")

    def test_fast_routes_to_groq(self):
        os.environ["GROQ_API_KEY"] = "groq-fake"
        os.environ["OPENROUTER_API_KEY"] = "or-fake"
        r = router.ModelRouter.route_request("summarize", "fast")
        self.assertEqual(r["provider"], "Groq")

    def test_general_routes_to_openrouter(self):
        os.environ["OPENROUTER_API_KEY"] = "or-fake"
        os.environ["DEEPSEEK_API_KEY"] = "dsk-fake"
        r = router.ModelRouter.route_request("analyze this problem", "general")
        self.assertEqual(r["provider"], "OpenRouter")

    def test_call_llm_payload_shape(self):
        os.environ["GROQ_API_KEY"] = "groq-fake"
        with mock.patch("router.requests.post") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            out = router.ModelRouter.call_llm("hello", task_type="fast")
        self.assertEqual(out, "ok")
        payload = m.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "openai/gpt-oss-120b")
        self.assertEqual(len(payload["messages"]), 2)

    def test_fallback_chain_when_primary_fails(self):
        os.environ["DEEPSEEK_API_KEY"] = "dsk-fake"
        os.environ["GROQ_API_KEY"] = "groq-fake"

        def fake_post(url, **kwargs):
            if "deepseek" in url:
                return mock.Mock(status_code=503)
            return mock.Mock(status_code=200, json=lambda: {"choices": [{"message": {"content": "recovered"}}]})

        with mock.patch("router.time.sleep"), mock.patch("router.requests.post", side_effect=fake_post):
            out = router.ModelRouter.call_llm("write html", task_type="code")
        self.assertEqual(out, "recovered")
        self.assertEqual(router.ModelRouter.last_route["provider"], "Groq")

    def test_retry_then_success(self):
        os.environ["GROQ_API_KEY"] = "groq-fake"
        calls = {"n": 0}

        def flaky(url, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return mock.Mock(status_code=429)
            return mock.Mock(status_code=200, json=lambda: {"choices": [{"message": {"content": "ok"}}]})

        with mock.patch("router.time.sleep"), mock.patch("router.requests.post", side_effect=flaky):
            out = router.ModelRouter.call_llm("hi", task_type="fast")
        self.assertEqual(out, "ok")
        self.assertEqual(calls["n"], 2)

    def test_non_retryable_fails_fast(self):
        os.environ["DEEPSEEK_API_KEY"] = "dsk-fake"
        os.environ["OPENROUTER_API_KEY"] = "or-fake"
        calls = {"n": 0}

        def dead(url, **kwargs):
            calls["n"] += 1
            return mock.Mock(status_code=402)

        with mock.patch("router.time.sleep") as sleep, mock.patch("router.requests.post", side_effect=dead):
            with self.assertRaises(RuntimeError):
                router.ModelRouter.call_llm("write html", task_type="code")
        # One attempt per provider, zero backoff sleeps, both skipped fast.
        self.assertEqual(calls["n"], 2)
        sleep.assert_not_called()

    def test_all_providers_exhausted_raises(self):
        os.environ["GROQ_API_KEY"] = "groq-fake"
        with mock.patch("router.time.sleep"), mock.patch(
            "router.requests.post", return_value=mock.Mock(status_code=500)
        ):
            with self.assertRaises(RuntimeError):
                router.ModelRouter.call_llm("hi", task_type="fast")


class TestReflection(unittest.TestCase):
    # Isolate memory writes in a temp file so tests never touch the real store.
    def setUp(self):
        clear_env()
        fd, self.tmp = tempfile.mkstemp(prefix="nexus_lessons_", suffix=".json")
        os.close(fd)
        self._orig = reflection.LESSONS_FILE
        reflection.LESSONS_FILE = self.tmp
        with open(self.tmp, "w", encoding="utf-8") as f:
            json.dump(reflection.DEFAULT_STATE, f)

    def tearDown(self):
        reflection.LESSONS_FILE = self._orig
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_stats_persist_even_if_reflection_fails(self):
        with mock.patch.object(router.ModelRouter, "call_llm", side_effect=RuntimeError("boom")):
            lesson = SelfReflection.record_execution("task", "output", success=True)
        self.assertIsNone(lesson)
        with open(reflection.LESSONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["total_runs"], 1)
        self.assertEqual(data["successful_runs"], 1)

    def test_deduplication(self):
        with mock.patch.object(router.ModelRouter, "call_llm", return_value="Always output strict dark mode."):
            SelfReflection.record_execution("task1", "out", success=True)
            SelfReflection.record_execution("task2", "out", success=True)
        with open(reflection.LESSONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["lessons"]), 1)
        self.assertEqual(data["total_runs"], 2)

    def test_load_memory_empty(self):
        self.assertIn("No previous lessons", SelfReflection.load_memory())

    def test_no_lesson_when_environment_only_event(self):
        with mock.patch.object(router.ModelRouter, "call_llm", return_value="NO_LESSON"):
            lesson = SelfReflection.record_execution("task", "output", success=True)
        self.assertIsNone(lesson)
        with open(reflection.LESSONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["lessons"]), 0)
        self.assertEqual(data["total_runs"], 1)


class TestAgentFlow(unittest.TestCase):
    def setUp(self):
        clear_env()
        # Isolate artifact writes in a temp dir so tests never touch the repo output/
        self._tmpout = tempfile.mkdtemp(prefix="nexus_out_")
        os.environ["OUTPUT_DIR"] = self._tmpout
        self._out = self._tmpout
        # Isolate memory writes
        fd, self.tmp = tempfile.mkstemp(prefix="nexus_lessons_", suffix=".json")
        os.close(fd)
        self._orig = reflection.LESSONS_FILE
        reflection.LESSONS_FILE = self.tmp
        with open(self.tmp, "w", encoding="utf-8") as f:
            json.dump(reflection.DEFAULT_STATE, f)

    def tearDown(self):
        reflection.LESSONS_FILE = self._orig
        if os.path.exists(self.tmp):
            os.remove(self.tmp)
        os.environ.pop("OUTPUT_DIR", None)
        shutil.rmtree(self._tmpout, ignore_errors=True)

    def test_chat_mode_conversational(self):
        reply = "Hey! I can build you a habit tracker, a dashboard, or anything single-file. What should we make?"
        with mock.patch.object(router.ModelRouter, "call_llm", return_value=reply):
            NexusAgent().process_task("hey what can you do", mode="chat")
        reports = glob.glob(os.path.join(self._out, "report_*.md"))
        self.assertTrue(reports)
        with open(reports[0], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("hey what can you do", content)
        self.assertIn("Hey!", content)
        # No HTML artifact expected for a conversational reply
        self.assertEqual(glob.glob(os.path.join(self._out, "app_*.html")), [])

    def test_chat_mode_build_produces_artifact(self):
        reply = 'Sure! Here is your tracker:\n```html\n<div class="app">Habit Tracker</div>\n```'
        with mock.patch.object(router.ModelRouter, "call_llm", side_effect=[reply, "NO_CHANGE", "lesson"]):
            NexusAgent().process_task("build me a habit tracker", mode="chat")
        apps = glob.glob(os.path.join(self._out, "app_*.html"))
        self.assertTrue(apps)

    def test_full_flow_with_mock_llm(self):
        fake = 'Here is the component:\n```html\n<div class="p-4 text-white">Nexus Dashboard</div>\n```'
        with mock.patch.object(router.ModelRouter, "call_llm", return_value=fake):
            agent = NexusAgent()
            agent.process_task("Build a dark dashboard", mode="full")

        reports = glob.glob(os.path.join(self._out, "report_*.md"))
        apps = glob.glob(os.path.join(self._out, "app_*.html"))
        manifests = glob.glob(os.path.join(self._out, "manifest_*.json"))
        self.assertTrue(reports)
        self.assertTrue(apps)
        self.assertTrue(manifests)

        with open(manifests[0], "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["provider"], "unknown")  # mocked, no real route
        self.assertIn("app_", manifest["artifacts"][0])
        self.assertIn("review", manifest)

        # Live-preview pointer files must exist for the Pages control surface
        self.assertTrue(glob.glob(os.path.join(self._out, "latest_app.html")))
        self.assertTrue(glob.glob(os.path.join(self._out, "latest_manifest.json")))
        self.assertTrue(glob.glob(os.path.join(self._out, "latest_report.md")))

        with open(reflection.LESSONS_FILE, "r", encoding="utf-8") as f:
            mem = json.load(f)
        self.assertGreaterEqual(mem["total_runs"], 1)

    def test_self_healing_retry_when_no_html(self):
        first = "Sorry, here is a description only."
        second = '```html\n<html><body class="bg-black"></body></html>\n```'
        with mock.patch.object(router.ModelRouter, "call_llm", side_effect=[first, second, "NO_CHANGE"]):
            agent = NexusAgent()
            agent.process_task("Build a landing page", mode="code")

        apps = glob.glob(os.path.join(self._out, "app_*.html"))
        self.assertTrue(apps)
        with open(apps[0], "r", encoding="utf-8") as f:
            self.assertIn("<html", f.read())

    def test_review_pass_applies_improvement(self):
        gen = '```html\n<div class="a">v1</div>\n```'
        improved = '```html\n<div class="b">v2 polished premium</div>\n```'
        with mock.patch.object(router.ModelRouter, "call_llm", side_effect=[gen, improved, "lesson"]):
            NexusAgent().process_task("Build a landing page", mode="code")

        with open(os.path.join(self._out, "latest_app.html"), "r", encoding="utf-8") as f:
            self.assertIn("v2 polished premium", f.read())
        with open(os.path.join(self._out, "latest_manifest.json"), "r", encoding="utf-8") as f:
            m = json.load(f)
        self.assertTrue(m["review"]["enabled"])
        self.assertTrue(m["review"]["applied"])

    def test_review_pass_skipped_when_disabled(self):
        os.environ["NEXUS_REVIEW"] = "0"
        gen = '```html\n<div class="a">v1</div>\n```'
        try:
            with mock.patch.object(router.ModelRouter, "call_llm", return_value=gen) as m:
                NexusAgent().process_task("Build a landing page", mode="code")
            self.assertEqual(m.call_count, 2)  # generation + reflection only
            with open(os.path.join(self._out, "latest_manifest.json"), "r", encoding="utf-8") as f:
                mm = json.load(f)
            self.assertFalse(mm["review"]["enabled"])
        finally:
            os.environ.pop("NEXUS_REVIEW", None)

    def test_review_no_change_keeps_artifact(self):
        gen = '```html\n<div class="a">v1</div>\n```'
        with mock.patch.object(router.ModelRouter, "call_llm", side_effect=[gen, "NO_CHANGE", "lesson"]):
            NexusAgent().process_task("Build a landing page", mode="code")
        with open(os.path.join(self._out, "latest_app.html"), "r", encoding="utf-8") as f:
            self.assertIn("v1", f.read())
        with open(os.path.join(self._out, "latest_manifest.json"), "r", encoding="utf-8") as f:
            m = json.load(f)
        self.assertFalse(m["review"]["applied"])


class TestSearch(unittest.TestCase):
    def test_disabled_without_key(self):
        clear_env()
        out = ResearchTool.search_web("anything")
        self.assertIn("Search Disabled", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
