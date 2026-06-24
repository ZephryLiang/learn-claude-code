"""Web search tool for deep research."""
import logging
from typing import Optional

logger = logging.getLogger("resume-editor.search")


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web for information.

    Uses a configurable search backend. Currently returns a placeholder.
    Replace with actual search API integration (SerpAPI, Tavily, etc.).
    """
    logger.info("Web search requested: query=%s max_results=%d", query, max_results)
    return [
        {"title": f"Search results for: {query}", "snippet": f"Results for '{query}' would appear here with a search API key configured."}
    ]
