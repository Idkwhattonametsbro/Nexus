import os
import time
import requests
from typing import Dict, Any, Optional

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

WORKFLOW = "run_agent.yml"
DEFAULT_REPO = "Idkwhattonametsbro/Nexus"


class NexusDispatch:
    """Remote control client for the Nexus pipeline.

    Used by the Telegram bot, the webhook bridge, and any external tool.
    Requires a GitHub token with Actions read/write on the target repository
    (a fine-grained personal access token scoped to the Nexus repo is best).
    """

    def __init__(self, repo: Optional[str] = None, token: Optional[str] = None):
        self.repo = repo or os.getenv("NEXUS_REPO") or DEFAULT_REPO
        self.token = token or os.getenv("NEXUS_GITHUB_TOKEN")
        if not self.token:
            raise ValueError("Missing token: set NEXUS_GITHUB_TOKEN (Actions read/write scope).")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def dispatch(self, prompt: str, mode: str = "full", ref: str = "main") -> Dict[str, Any]:
        """Trigger the pipeline via workflow_dispatch and return the created run."""
        url = f"{API}/repos/{self.repo}/actions/workflows/{WORKFLOW}/dispatches"
        res = requests.post(
            url,
            headers=self._headers(),
            json={"ref": ref, "inputs": {"prompt": prompt, "mode": mode}},
            timeout=30,
        )
        res.raise_for_status()
        # Locate the run that was just created (newest dispatch).
        for _ in range(12):
            runs = requests.get(
                f"{API}/repos/{self.repo}/actions/runs",
                headers=self._headers(),
                params={"event": "workflow_dispatch", "per_page": 1},
                timeout=30,
            ).json().get("workflow_runs", [])
            if runs:
                return runs[0]
            time.sleep(2)
        raise RuntimeError("Run dispatched but not yet visible via the API.")

    def run_status(self, run_id: int) -> Dict[str, Any]:
        res = requests.get(
            f"{API}/repos/{self.repo}/actions/runs/{run_id}",
            headers=self._headers(),
            timeout=30,
        )
        res.raise_for_status()
        return res.json()

    def poll(self, run_id: int, interval: int = 15, timeout: int = 900) -> Dict[str, Any]:
        """Block until the run completes. Returns the final run object."""
        waited = 0
        while waited < timeout:
            run = self.run_status(run_id)
            if run.get("status") == "completed":
                return run
            time.sleep(interval)
            waited += interval
        raise TimeoutError(f"Run {run_id} did not complete within {timeout}s.")

    def latest_manifest(self) -> Optional[Dict[str, Any]]:
        """Fetch the latest run manifest from the default branch (public repos)."""
        url = f"{RAW}/{self.repo}/main/output/latest_manifest.json"
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                return res.json()
        except requests.RequestException:
            pass
        return None

    def summarize(self, run: Dict[str, Any]) -> str:
        """Human-readable one-liner for chat surfaces."""
        status = run.get("status", "?")
        conclusion = run.get("conclusion")
        run_id = run.get("id")
        url = run.get("html_url", "")
        if status == "completed":
            outcome = conclusion or "?"
            return f"Run #{run_id}: {outcome.upper()} - {url}"
        return f"Run #{run_id}: {status.upper()} - {url}"
