import asyncio

from operator_use.tools.service import Tool, ToolResult, MAX_TOOL_OUTPUT_LENGTH
from pydantic import BaseModel, Field
from urllib.parse import urlparse
from ddgs import DDGS
import httpx

ddgs = DDGS()

# Max chars to send to LLM for extraction — keeps cost low
_EXTRACT_LIMIT = 24_000


class WebSearch(BaseModel):
    query: str = Field(..., description="The search query. Be specific — include names, versions, or error messages for better results.")
    max_results: int = Field(default=10, description="Number of results to return (default 10). Increase to 20+ when you need broader coverage, decrease to 3-5 for quick lookups.")


@Tool(name="web_search", description="Search the web using DuckDuckGo and return titles, URLs, and snippets. Results are biased toward the last 3 days. Use for current events, documentation, package info, or error messages. Follow up with web_fetch to read the full content of a result.", model=WebSearch)
async def web_search(query: str, max_results: int = 10, **kwargs) -> ToolResult:
    try:
        results = await asyncio.to_thread(lambda: ddgs.text(
            query,
            region="us-en",
            safesearch="off",
            timelimit="3d",
            backend="auto",
            max_results=max_results,
        ))
    except Exception as e:
        return ToolResult.error_result(f"Failed to search the web: {e}")

    if not results:
        return ToolResult.success_result(f"No results found for: {query}")

    lines = [f"🔍 Web Search Results for: {query}"]
    for idx, result in enumerate(results, start=1):
        lines.append(f"🔍 {idx}. Title: {result['title']}")
        lines.append(f"   URL: {result['href']}")
        if result.get('body'):
            lines.append(f"   Snippet: {result['body']}")
        lines.append("")

    return ToolResult.success_result("\n".join(lines))


def _html_to_markdown(html: str) -> str:
    """Convert HTML to markdown using markdownify."""
    from markdownify import markdownify
    return markdownify(html, heading_style="ATX", strip=["script", "style", "nav", "footer", "header"])


async def _extract_relevant(text: str, prompt: str, llm) -> str:
    """Use LLM to extract the relevant portion of a page for the given prompt."""
    from operator_use.messages.service import SystemMessage, HumanMessage
    from operator_use.providers.events import LLMEventType

    truncated = text[:_EXTRACT_LIMIT]
    messages = [
        SystemMessage(content="You are a precise text extractor. Extract only the information relevant to the user's query from the provided page content. Be concise. If the information is not present, say so clearly."),
        HumanMessage(content=f"Query: {prompt}\n\nPage content:\n{truncated}"),
    ]
    try:
        event = await llm.ainvoke(messages=messages,)
        if event.type == LLMEventType.TEXT and event.content:
            return event.content
    except Exception:
        pass
    return text


class WebFetch(BaseModel):
    url: str = Field(..., description="Full URL to fetch (must start with http:// or https://). Redirects are followed automatically.")
    prompt: str | None = Field(
        default=None,
        description=(
            "If provided, the page is passed to the LLM which extracts only the relevant parts. "
            "Use when you know what you're looking for — e.g. 'current temperature in Singapore', 'latest release version'. "
            "Omit for APIs, JSON endpoints, or when you need the raw content."
        ),
    )
    timeout: int = Field(default=10, description="Request timeout in seconds (default 10). Increase to 30+ for slow APIs or large pages.")


@Tool(
    name="web_fetch",
    description=(
        "Fetch the content of a URL and return it as text. Use after web_search to read a full page. "
        "Also useful for REST APIs, config files, and documentation. "
        "Set prompt= to extract only what you need from the page — the LLM will filter out irrelevant content. "
        "Omit prompt for raw output (JSON APIs, downloads, etc.)."
    ),
    model=WebFetch,
)
async def web_fetch(url: str, prompt: str | None = None, timeout: int = 10, **kwargs) -> ToolResult:
    parsed_url = urlparse(url)
    if not parsed_url.scheme or parsed_url.scheme not in ['http', 'https']:
        return ToolResult.error_result(f"Invalid URL: {url}. Must be http:// or https://")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            text = response.text
    except httpx.TimeoutException:
        return ToolResult.error_result(f"Request timed out after {timeout} seconds. Try increasing timeout.")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 403:
            return ToolResult.error_result(
                f"403 Forbidden: the site is blocking automated requests. "
                f"Try a different URL, search for a cached version, or use web.search snippets instead."
            )
        if status == 404:
            return ToolResult.error_result(f"404 Not Found: the page does not exist at {url}")
        if status == 429:
            return ToolResult.error_result(f"429 Too Many Requests: rate limited. Wait before retrying.")
        return ToolResult.error_result(f"HTTP {status}: {e.response.reason_phrase}")
    except httpx.RequestError as e:
        return ToolResult.error_result(f"Request error: {e}")
    except Exception as e:
        return ToolResult.error_result(f"Error: {e}")

    text = _html_to_markdown(text)

    # LLM extraction when prompt is provided
    llm = kwargs.get("_llm")
    if prompt and llm:
        text = await _extract_relevant(text, prompt, llm)
    elif len(text) > MAX_TOOL_OUTPUT_LENGTH:
        text = text[:MAX_TOOL_OUTPUT_LENGTH] + "..."

    return ToolResult.success_result(text)
