"""
Dual search: Tavily (primary) with DuckDuckGo as automatic fallback.
Both are wrapped as LangChain tools for use inside ReAct agents.
"""
from __future__ import annotations
import logging
from typing import Any

from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from duckduckgo_search import DDGS

from app.config import get_settings

logger = logging.getLogger(__name__)


# ── Tavily (primary) ─────────────────────────────────────────────────────────

def get_tavily_tool(max_results: int = 4) -> TavilySearchResults:
    s = get_settings()
    if not s.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY not set")
    return TavilySearchResults(
        max_results=max_results,
        api_key=s.tavily_api_key,
        include_answer=True,
        include_raw_content=False,
    )


# ── DuckDuckGo (backup, no key) ──────────────────────────────────────────────

def _ddg_search(query: str, max_results: int = 4) -> list[dict[str, str]]:
    """Raw DuckDuckGo search returning list of {title, url, snippet}."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "content": r.get("body", ""),
            })
    return results


# ── Combined tool with automatic fallback ────────────────────────────────────

@tool
def web_search(query: str) -> str:
    """
    Search the web for current information about Egypt tourism.
    Tries Tavily first; falls back to DuckDuckGo automatically.

    Args:
        query: The search query string.

    Returns:
        Formatted string with search results.
    """
    s = get_settings()

    # ── Try Tavily ────────────────────────────────────────────────────────────
    if s.tavily_api_key:
        try:
            tavily = get_tavily_tool()
            results: Any = tavily.invoke(query)
            if results:
                formatted = "\n\n".join(
                    f"[{r.get('title', 'No title')}]\n{r.get('content', '')}\nSource: {r.get('url', '')}"
                    for r in results
                )
                return f"[Tavily Search Results]\n{formatted}"
        except Exception as e:
            logger.warning("Tavily search failed (%s), falling back to DuckDuckGo", e)

    # ── Fallback: DuckDuckGo ──────────────────────────────────────────────────
    try:
        results = _ddg_search(query)
        if results:
            formatted = "\n\n".join(
                f"[{r['title']}]\n{r['content']}\nSource: {r['url']}"
                for r in results
            )
            return f"[DuckDuckGo Search Results]\n{formatted}"
    except Exception as e:
        logger.error("DuckDuckGo fallback also failed: %s", e)

    return "No search results found. Please try a different query."