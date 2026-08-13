import os
import sys
import json
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

import nexus_dispatch
from nexus_dispatch import NexusDispatch


class TestNexusDispatch(unittest.TestCase):
    def setUp(self):
        os.environ["NEXUS_GITHUB_TOKEN"] = "fake-token"
        os.environ["NEXUS_REPO"] = "test/repo"
        self.d = NexusDispatch()

    def tearDown(self):
        os.environ.pop("NEXUS_GITHUB_TOKEN", None)
        os.environ.pop("NEXUS_REPO", None)

    def test_missing_token_raises(self):
        os.environ.pop("NEXUS_GITHUB_TOKEN", None)
        with self.assertRaises(ValueError):
            NexusDispatch()

    def test_dispatch_posts_correct_payload(self):
        fake_run = {"id": 42, "run_number": 7, "html_url": "https://github.com/test/repo/actions/runs/42"}
        with mock.patch("nexus_dispatch.requests.post") as post, mock.patch(
            "nexus_dispatch.requests.get"
        ) as get:
            post.return_value = mock.Mock(status_code=204)
            get.return_value.json.return_value = {"workflow_runs": [fake_run]}

            run = self.d.dispatch("build a dashboard", mode="full")

        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertIn("/actions/workflows/run_agent.yml/dispatches", args[0])
        self.assertEqual(kwargs["json"]["inputs"]["prompt"], "build a dashboard")
        self.assertEqual(kwargs["json"]["inputs"]["mode"], "full")
        self.assertEqual(run["id"], 42)

    def test_poll_returns_on_completion(self):
        states = iter([
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success", "id": 42},
        ])
        with mock.patch.object(self.d, "run_status", side_effect=lambda rid: next(states)), \
             mock.patch("time.sleep"):
            run = self.d.poll(42, interval=1, timeout=30)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["conclusion"], "success")

    def test_poll_times_out(self):
        with mock.patch.object(self.d, "run_status", return_value={"status": "in_progress"}), \
             mock.patch("time.sleep"):
            with self.assertRaises(TimeoutError):
                self.d.poll(42, interval=1, timeout=2)

    def test_latest_manifest(self):
        manifest = {"provider": "Groq", "latency_ms": 100}
        with mock.patch("nexus_dispatch.requests.get") as get:
            get.return_value.status_code = 200
            get.return_value.json.return_value = manifest
            out = self.d.latest_manifest()
        self.assertEqual(out["provider"], "Groq")

    def test_summarize(self):
        self.assertIn(
            "SUCCESS",
            self.d.summarize({"status": "completed", "conclusion": "success", "id": 3}),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
