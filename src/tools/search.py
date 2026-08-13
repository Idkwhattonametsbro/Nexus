import os
import requests


class ResearchTool:
    @staticmethod
    def search_web(query: str) -> str:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "[Search Disabled: TAVILY_API_KEY missing]"

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 3
        }

        try:
            res = requests.post(url, json=payload, timeout=15)
            res.raise_for_status()
            results = res.json().get("results", [])

            output = []
            for item in results:
                output.append(f"- {item['title']}: {item['content']} ({item['url']})")
            return "\n".join(output) if output else "No relevant results found."
        except Exception as e:
            return f"[Search Error: {str(e)}]"
