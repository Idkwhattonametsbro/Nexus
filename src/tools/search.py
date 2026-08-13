import os
import requests


class ResearchTool:
    MAX_RESULTS = 3
    MAX_SNIPPET = 300

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
            "max_results": ResearchTool.MAX_RESULTS,
        }

        try:
            res = requests.post(url, json=payload, timeout=15)
            res.raise_for_status()
            results = res.json().get("results", [])

            output = []
            for item in results[: ResearchTool.MAX_RESULTS]:
                title = item.get("title", "").strip()
                content = (item.get("content") or "").strip()
                link = item.get("url", "").strip()
                if not title or not link:
                    continue
                if len(content) > ResearchTool.MAX_SNIPPET:
                    content = content[: ResearchTool.MAX_SNIPPET] + "..."
                output.append(f"- {title}: {content} ({link})")
            return "\n".join(output) if output else "No relevant results found."
        except Exception as e:
            return f"[Search Error: {str(e)}]"
