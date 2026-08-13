import os
import time
import requests
from typing import Dict, Any, List, Optional

DEFAULT_TIMEOUT = 60
MAX_ATTEMPTS = 3
BACKOFF_BASE = 2.0

# Non-retryable client errors (bad key, no credit, forbidden...). Failing fast
# on these keeps the fallback chain snappy when a provider is dead (e.g. 402).
NON_RETRYABLE = {400, 401, 402, 403, 404}

# Ordered fallback chains per task type. The first provider whose key is
# configured is the primary route; every subsequent entry is a self-healing
# fallback if the primary provider fails or rate-limits.
CHAINS: Dict[str, List[str]] = {
    "code": ["DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"],
    "fast": ["GROQ_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"],
    "general": ["OPENROUTER_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY"],
}

# Current-generation models (verified August 2026).
# DeepSeek: legacy deepseek-chat was discontinued 2026-07-24; v4 line is current.
# Groq: llama-4-maverick deprecated 2026-03-09 in favor of gpt-oss-120b.
# OpenRouter: Claude Sonnet 4.6 is the current agentic-coding flagship.
PROVIDERS: Dict[str, Dict[str, str]] = {
    "DEEPSEEK_API_KEY": {
        "provider": "DeepSeek",
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-v4-pro",
    },
    "GROQ_API_KEY": {
        "provider": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": "GROQ_API_KEY",
        "model": "openai/gpt-oss-120b",
    },
    "OPENROUTER_API_KEY": {
        "provider": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "anthropic/claude-sonnet-4.6",
    },
    "OPENAI_API_KEY": {
        "provider": "OpenAI",
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
    },
}

# Optional per-provider model overrides via environment.
MODEL_OVERRIDES = {
    "DEEPSEEK_API_KEY": "NEXUS_MODEL_DEEPSEEK",
    "GROQ_API_KEY": "NEXUS_MODEL_GROQ",
    "OPENROUTER_API_KEY": "NEXUS_MODEL_OPENROUTER",
    "OPENAI_API_KEY": "NEXUS_MODEL_OPENAI",
}


class ModelRouter:
    last_route: Optional[Dict[str, Any]] = None

    @staticmethod
    def _model_for(env_key: str) -> str:
        override = os.getenv(MODEL_OVERRIDES[env_key])
        return override or PROVIDERS[env_key]["model"]

    @staticmethod
    def _effective_task_type(prompt: str, task_type: str) -> str:
        if task_type in ("code", "fast", "general"):
            return task_type
        if task_type == "research_only":
            return "fast"
        lowered = prompt.lower()
        code_signals = (
            "code", "html", "css", "javascript", "python", "app",
            "dashboard", "component", "script", "website", "ui",
            "frontend", "backend", "api", "database", "docker", "repository",
        )
        if any(s in lowered for s in code_signals):
            return "code"
        return "general"

    @staticmethod
    def _candidates(task_type: str) -> List[Dict[str, Any]]:
        candidates = []
        for env_key in CHAINS.get(task_type, CHAINS["general"]):
            api_key = os.getenv(env_key)
            if api_key:
                spec = dict(PROVIDERS[env_key])
                spec["key"] = api_key
                spec["model"] = ModelRouter._model_for(env_key)
                candidates.append(spec)
        return candidates

    @staticmethod
    def route_request(prompt: str, task_type: str = "general") -> Dict[str, Any]:
        """Return the primary (highest priority) configured route for the task."""
        effective = ModelRouter._effective_task_type(prompt, task_type)
        candidates = ModelRouter._candidates(effective)
        if not candidates:
            raise ValueError("System Error: No valid API keys found in environment variables.")
        return candidates[0]

    @staticmethod
    def diagnose() -> Dict[str, Any]:
        """Health report of configured providers and their roles."""
        configured = [
            {"provider": p["provider"], "model": ModelRouter._model_for(k)}
            for k, p in PROVIDERS.items() if os.getenv(k)
        ]
        return {
            "configured_providers": configured,
            "routes": {k: len(ModelRouter._candidates(k)) for k in CHAINS},
        }

    @classmethod
    def call_llm(
        cls,
        prompt: str,
        system_prompt: str = "You are Nexus. Output functional code and objective analysis.",
        task_type: str = "general",
        temperature: float = 0.2,
    ) -> str:
        effective = cls._effective_task_type(prompt, task_type)
        candidates = cls._candidates(effective)
        if not candidates:
            raise ValueError("System Error: No valid API keys found in environment variables.")

        errors: List[str] = []
        for candidate in candidates:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    headers = {
                        "Authorization": f"Bearer {candidate['key']}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": candidate["model"],
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": temperature,
                    }
                    response = requests.post(
                        candidate["url"], headers=headers, json=payload, timeout=DEFAULT_TIMEOUT
                    )

                    if response.status_code == 200:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        cls.last_route = candidate
                        print(f"[Route] Success via {candidate['provider']} ({candidate['model']})")
                        return content

                    if response.status_code in NON_RETRYABLE:
                        errors.append(f"{candidate['provider']}: HTTP {response.status_code} (non-retryable)")
                        print(f"[Route] {candidate['provider']} HTTP {response.status_code} - skipping, moving down the chain")
                        break

                    if response.status_code in (429, 500, 502, 503, 504):
                        errors.append(f"{candidate['provider']}: HTTP {response.status_code} (attempt {attempt})")
                        print(f"[Route] {candidate['provider']} HTTP {response.status_code} - retrying in {BACKOFF_BASE ** attempt:.0f}s")
                        time.sleep(BACKOFF_BASE ** attempt)
                        continue

                    response.raise_for_status()
                except (requests.RequestException, KeyError, ValueError) as e:
                    errors.append(f"{candidate['provider']}: {e}")
                    print(f"[Route] {candidate['provider']} failed: {e}")
                    time.sleep(BACKOFF_BASE ** attempt)

        raise RuntimeError("All providers exhausted: " + " | ".join(errors))
