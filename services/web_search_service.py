"""Web search service using DuckDuckGo. Returns formatted snippets
for injection into the response system prompt."""

from duckduckgo_search import DDGS
from config import Config


def search(query, max_results=None):
    """Run a general web search. Returns a formatted string of results."""
    max_results = max_results or Config.WEB_SEARCH_MAX_RESULTS
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return ""

    if not results:
        return ""

    return _format_results(results)


def search_news(query, max_results=None):
    """Search recent news articles."""
    max_results = max_results or Config.WEB_SEARCH_MAX_RESULTS
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
    except Exception:
        return ""

    if not results:
        return ""

    return _format_results(results)


def _format_results(results):
    """Format search results into a readable block for the LLM."""
    lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body") or r.get("description") or ""
        url = r.get("href") or r.get("url") or ""
        lines.append(f"- {title}: {body} ({url})")
    return "\n".join(lines)
