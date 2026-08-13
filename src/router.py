import os
import requests
from typing import Dict, Any


class ModelRouter:
    @staticmethod
    def route_request(prompt: str, task_type: str = "general") -> Dict[str, Any]:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")

        if (task_type == "code" or "code" in prompt.lower() or "html" in prompt.lower()) and deepseek_key:
            return {
                "provider": "DeepSeek",
                "url": "https://api.deepseek.com/chat/completions",
                "key": deepseek_key,
                "model": "deepseek-chat"
            }
        elif task_type == "fast" and groq_key:
            return {
                "provider": "Groq",
                "url": "https://api.groq.com/openai/v1/chat/completions",
                "key": groq_key,
                "model": "llama-3.3-70b-versatile"
            }
        elif openrouter_key:
            return {
                "provider": "OpenRouter",
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "key": openrouter_key,
                "model": "anthropic/claude-3.5-sonnet"
            }
        else:
            raise ValueError("System Error: No valid API keys found in environment variables.")

    @classmethod
    def call_llm(cls, prompt: str, system_prompt: str = "You are Nexus. Output functional code and objective analysis.", task_type: str = "general") -> str:
        route = cls.route_request(prompt, task_type)
        headers = {
            "Authorization": f"Bearer {route['key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": route["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        response = requests.post(route["url"], headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
