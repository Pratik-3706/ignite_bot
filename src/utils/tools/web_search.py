import asyncio
from typing import Optional
from tavily import TavilyClient
from src.config import TAVILY_API_KEY

_tavily_client: Optional[TavilyClient] = None

def get_tavily_client() -> Optional[TavilyClient]:
    global _tavily_client
    if _tavily_client is None and TAVILY_API_KEY:
        _tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    return _tavily_client

async def search_web(query: str, max_results: int = 4) -> str:
    client = get_tavily_client()
    if not client:
        return "Web search is disabled (TAVILY_API_KEY is not configured)."

    def _execute():
        try:
            response = client.search(query=query, max_results=max_results, search_depth="basic")
            results = response.get("results", [])
            if not results:
                return f"No relevant web search results found for: '{query}'."

            formatted = []
            for idx, r in enumerate(results, 1):
                title = r.get("title", "Untitled")
                url = r.get("url", "")
                snippet = r.get("content", "").strip()
                formatted.append(f"{idx}. [{title}]({url})\n   {snippet}")
            return "\n\n".join(formatted)
        except Exception as e:
            return f"Web search failed: {str(e)}"

    return await asyncio.to_thread(_execute)
