import asyncio
from typing import Any


def _sync_search(query: str, timeout: float) -> list[dict[str, Any]]:
    """Run the blocking ddgs text search and return raw result dicts."""
    from ddgs import DDGS

    with DDGS(timeout=int(timeout)) as ddgs:
        return list(ddgs.text(query, max_results=5))


async def search(query: str, timeout: float = 8.0) -> str:
    """Search DuckDuckGo via the maintained ddgs package.

    Only the short query string (<80 chars) ever leaves the backend.
    Returns up to 5 results as plain text (title + snippet),
    or an empty string if no results are found.

    Raises:
        asyncio.TimeoutError: If the search exceeds the timeout.
    """
    cleaned_query = query.strip() if query else ""
    if not cleaned_query:
        return ""
    short_query = cleaned_query[:80]

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_sync_search, short_query, timeout),
            timeout=timeout,
        )
    except (asyncio.TimeoutError, TimeoutError) as exc:
        raise asyncio.TimeoutError("DuckDuckGo search timed out") from exc
    except Exception:
        return ""

    if not results:
        return ""

    lines: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title", "")).split())
        snippet = " ".join(str(item.get("body", "")).split())
        if title and snippet:
            lines.append(f"{title}\n{snippet}")
        elif title:
            lines.append(title)
        elif snippet:
            lines.append(snippet)

    return "\n\n".join(lines)
