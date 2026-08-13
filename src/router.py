import os
import re
import time
import base64
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
    "code": [
        "DEEPSEEK_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
        "OPENAI_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "GITHUB_MODELS_TOKEN",
    ],
    "fast": [
        "GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY", "GITHUB_MODELS_TOKEN",
        "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY",
    ],
    "general": [
        "GEMINI_API_KEY", "OPENROUTER_API_KEY", "GITHUB_MODELS_TOKEN",
        "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY",
    ],
}

# Current-generation models (verified August 2026).
# DeepSeek: legacy deepseek-chat was discontinued 2026-07-24; v4 line is current.
# Groq: llama-4-maverick deprecated 2026-03-09 in favor of gpt-oss-120b.
# Gemini 2.5 Flash: free tier (no card), strong coding + vision.
# GitHub Models: free with any GitHub PAT (models.inference.ai.azure.com).
# Cerebras: free tier, Llama 3.3 70B.
PROVIDERS: Dict[str, Dict[str, Any]] = {
    "DEEPSEEK_API_KEY": {
        "provider": "DeepSeek",
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-v4-pro",
        "vision": False,
    },
    "GEMINI_API_KEY": {
        "provider": "Google",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-2.5-flash",
        "vision": True,
    },
    "OPENROUTER_API_KEY": {
        "provider": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "anthropic/claude-sonnet-4.6",
        "vision": True,
    },
    "OPENAI_API_KEY": {
        "provider": "OpenAI",
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "vision": True,
    },
    "GROQ_API_KEY": {
        "provider": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
        "vision": True,
    },
    "CEREBRAS_API_KEY": {
        "provider": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama-3.3-70b",
        "vision": False,
    },
    "GITHUB_MODELS_TOKEN": {
        "provider": "GitHubModels",
        "url": "https://models.inference.ai.azure.com/chat/completions",
        "model": "gpt-4.1-mini",
        "vision": True,
    },
}

# Optional per-provider model overrides via environment.
MODEL_OVERRIDES = {
    "DEEPSEEK_API_KEY": "NEXUS_MODEL_DEEPSEEK",
    "GEMINI_API_KEY": "NEXUS_MODEL_GEMINI",
    "OPENROUTER_API_KEY": "NEXUS_MODEL_OPENROUTER",
    "OPENAI_API_KEY": "NEXUS_MODEL_OPENAI",
    "GROQ_API_KEY": "NEXUS_MODEL_GROQ",
    "CEREBRAS_API_KEY": "NEXUS_MODEL_CEREBRAS",
    "GITHUB_MODELS_TOKEN": "NEXUS_MODEL_GITHUB",
}

IMAGE_URL_RE = re.compile(r"\[IMAGE_URL:\s*([^\]]+)\]")
DATA_URI_RE = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+")

_MIME_BY_EXT = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}


def _fetch_image(url: str) -> str:
    """Download an image URL and return a data URI for multimodal payloads."""
    try:
        res = requests.get(url, timeout=30)
        res.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch image {url}: {e}") from e
    ctype = res.headers.get("Content-Type", "")
    if not ctype or not ctype.startswith("image/"):
        ext = os.path.splitext(url.split("?")[0])[1].lower()
        ctype = _MIME_BY_EXT.get(ext, "image/png")
    b64 = base64.b64encode(res.content).decode()
    return f"data:{ctype};base64,{b64}"


def _collect_images(prompt: str) -> List[str]:
    """Extract [IMAGE_URL: ...] tokens and inline data URIs into data-URI parts."""
    parts: List[str] = []
    for url in IMAGE_URL_RE.findall(prompt):
        url = url.strip()
        if url.startswith("data:image/"):
            parts.append(url)
        else:
            parts.append(_fetch_image(url))
    for uri in DATA_URI_RE.findall(prompt):
        if uri not in parts:
            parts.append(uri)
    return parts


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
                spec["env"] = env_key
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

        # Multimodal support: images referenced via [IMAGE_URL: ...] or data URIs.
        images = []
        clean_prompt = prompt
        if IMAGE_URL_RE.search(prompt) or DATA_URI_RE.search(prompt):
            candidates = [c for c in candidates if c["env"] and PROVIDERS.get(c["env"], {}).get("vision")]
            if not candidates:
                raise RuntimeError(
                    "No vision-capable provider configured for image input. "
                    "Add GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY or GITHUB_MODELS_TOKEN."
                )
            images = _collect_images(prompt)
            clean_prompt = IMAGE_URL_RE.sub("", prompt).strip()
            clean_prompt = DATA_URI_RE.sub("", clean_prompt).strip()

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
                    if images:
                        content: Any = [{"type": "text", "text": clean_prompt or "(image attached)"}]
                        for uri in images:
                            content.append({"type": "image_url", "image_url": {"url": uri}})
                    else:
                        content = prompt
                    payload = {
                        "model": candidate["model"],
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": content},
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
