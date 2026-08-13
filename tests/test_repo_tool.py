import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

import repo_tool
from repo_tool import GitHubRepoTool


class TestGitHubRepoTool(unittest.TestCase):
    def setUp(self):
        os.environ.pop("NEXUS_GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_TOKEN", None)

    def test_available_false_without_token(self):
        self.assertFalse(GitHubRepoTool.available())

    def test_no_token_returns_honest_message(self):
        result = GitHubRepoTool.create_repo("test-repo", files={"a.txt": "x"})
        self.assertEqual(result["status"], "no_token")
        self.assertIn("NEXUS_GITHUB_TOKEN", result["message"])
        self.assertIn("no GitHub token", result["message"])

    def test_create_repo_full_flow(self):
        os.environ["NEXUS_GITHUB_TOKEN"] = "fake"
        responses = {
            "/user/repos": mock.Mock(status_code=201, json=lambda: {"html_url": "https://github.com/u/r", "full_name": "u/r"}),
        }

        def fake_post(url, **kwargs):
            path = url.split("api.github.com")[-1]
            if path == "/user/repos":
                return mock.Mock(status_code=201, json=lambda: {"html_url": "https://github.com/u/r", "full_name": "u/r"})
            if path.endswith("/git/blobs"):
                return mock.Mock(status_code=201, json=lambda: {"sha": "blob1"})
            if path.endswith("/git/trees"):
                return mock.Mock(status_code=201, json=lambda: {"sha": "tree1"})
            if path.endswith("/git/commits"):
                return mock.Mock(status_code=201, json=lambda: {"sha": "commit1"})
            if path.endswith("/git/refs"):
                return mock.Mock(status_code=201, json=lambda: {"ref": "refs/heads/main"})
            raise AssertionError(f"Unexpected URL: {url}")

        with mock.patch("repo_tool.requests.post", side_effect=fake_post), mock.patch("repo_tool.requests.get", return_value=mock.Mock(status_code=200, json=lambda: {"login": "u"})):
            result = GitHubRepoTool.create_repo("My Repo", description="desc", files={"a.txt": "x", "b.py": "y"})
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["url"], "https://github.com/u/r")

    def test_error_surface(self):
        os.environ["NEXUS_GITHUB_TOKEN"] = "fake"
        with mock.patch("repo_tool.requests.post", return_value=mock.Mock(status_code=422, json=lambda: {"message": "name already exists"})), \
             mock.patch("repo_tool.requests.get", return_value=mock.Mock(status_code=404)):
            result = GitHubRepoTool.create_repo("taken")
        self.assertEqual(result["status"], "error")
        self.assertIn("name already exists", result["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
