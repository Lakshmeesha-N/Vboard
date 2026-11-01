import asyncio
import html
from html.parser import HTMLParser
from typing import List, Tuple

import httpx

DUCKDUCKGO_SEARCH_URL = "https://html.duckduckgo.com/html/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class DuckDuckGoHTMLParser(HTMLParser):
    """HTML parser for extracting organic search results from DuckDuckGo."""

    def __init__(self) -> None:
        super().__init__()
        self.results: List[Tuple[str, str]] = []
        self._current_title: List[str] = []
        self._current_snippet: List[str] = []
        self._in_title = False
        self._in_snippet = False
        self._in_result = False
        self._is_ad = False
        self._result_depth = 0
        self._depth = 0

    def _save_current(self) -> None:
        if not self._is_ad:
            title = " ".join("".join(self._current_title).split())
            snippet = " ".join("".join(self._current_snippet).split())
            if title or snippet:
                self.results.append((html.unescape(title), html.unescape(snippet)))
        self._in_result = False
        self._is_ad = False
        self._current_title = []
        self._current_snippet = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._depth += 1
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()

        if tag == "div" and "result" in classes:
            if self._in_result:
                self._save_current()
            self._in_result = True
            self._result_depth = self._depth
            self._is_ad = any("ad" in c.lower() for c in classes)
            self._current_title = []
            self._current_snippet = []

        if self._in_result and not self._is_ad:
            if "result__a" in classes:
                self._in_title = True
                self._current_title = []
            elif "result__snippet" in classes:
                self._in_snippet = True
                self._current_snippet = []

    def handle_endtag(self, tag: str) -> None:
        if self._in_title and tag == "a":
            self._in_title = False
        elif self._in_snippet and tag == "a":
            self._in_snippet = False

        if tag == "div" and self._in_result and self._depth == self._result_depth:
            self._save_current()

        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_result and not self._is_ad:
            if self._in_title:
                self._current_title.append(data)
            elif self._in_snippet:
                self._current_snippet.append(data)

    def close(self) -> None:
        super().close()
        if self._in_result:
            self._save_current()


async def search(query: str, timeout: float = 8.0) -> str:
    """Search DuckDuckGo HTML endpoint and return top 3 snippets as plain text.

    Args:
        query: Outbound search query string.
        timeout: Maximum seconds to wait before raising TimeoutError.

    Returns:
        Top 3 search results formatted as plain text (title + snippet),
        or an empty string if no results are found.

    Raises:
        asyncio.TimeoutError: If the search request times out.
    """
    cleaned_query = query.strip() if query else ""
    if not cleaned_query:
        return ""

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await asyncio.wait_for(
                client.post(
                    DUCKDUCKGO_SEARCH_URL,
                    data={"q": cleaned_query},
                    headers=headers,
                    follow_redirects=True,
                ),
                timeout=timeout,
            )
    except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
        raise asyncio.TimeoutError("DuckDuckGo search timed out") from exc
    except Exception:
        return ""

    if response.status_code != 200 or not response.text:
        return ""

    parser = DuckDuckGoHTMLParser()
    try:
        parser.feed(response.text)
        parser.close()
    except Exception:
        return ""

    if not parser.results:
        return ""

    lines: List[str] = []
    for title, snippet in parser.results[:3]:
        if title and snippet:
            lines.append(f"{title}\n{snippet}")
        elif title:
            lines.append(title)
        elif snippet:
            lines.append(snippet)

    return "\n\n".join(lines)
