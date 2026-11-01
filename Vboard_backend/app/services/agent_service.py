import asyncio
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.core.exceptions import InvalidRequestError, MetaApiError, RateLimitedError
from app.services import llm_service, search_service

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current facts, information, or context.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string to submit.",
                }
            },
            "required": ["query"],
        },
    },
}

OUT_OF_SCOPE_MARKER = "[[OUT_OF_SCOPE]]"


@dataclass
class AgentResult:
    text: str
    used_search: bool
    rounds: int
    note: Optional[str]
    elapsed_ms: float


def _load_prompt(filename: str) -> str:
    """Load prompt content from app/prompts directory."""
    path = _PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def route(content: str) -> str:
    """Determine branch based on whether content starts with @agent."""
    if content.lstrip().lower().startswith("@agent"):
        return "agent"
    return "cleanup"


def parse_agent_block(content: str) -> tuple[str, str]:
    """Parse task and body from content after stripping @agent directive."""
    lines = content.splitlines()
    start_idx = 0
    inline_task = ""
    found_agent = False

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("@agent"):
            found_agent = True
            start_idx = idx + 1
            after = re.sub(r"(?i)^@agent\s*", "", stripped).strip()
            if after:
                inline_task = after
            break

    remaining = lines[start_idx:] if found_agent else lines
    if inline_task:
        body = "\n".join(remaining)
        return (inline_task, body)

    task_idx = None
    for idx, line in enumerate(remaining):
        if line.strip():
            task_idx = idx
            break

    if task_idx is None:
        return ("", "")

    task = remaining[task_idx].strip()
    body = "\n".join(remaining[task_idx + 1:])
    return (task, body)


async def cleanup_branch(
    content: str, languages: Optional[str] = None
) -> AgentResult:
    """Execute grammar, punctuation, and translation cleanup using LLM."""
    system_prompt = _load_prompt("cleanup_system.md")

    async def _call_complete() -> llm_service.LLMResult:
        return await llm_service.complete(
            system_prompt, content, reasoning_effort="minimal"
        )

    try:
        result = await _call_complete()
    except RateLimitedError:
        raise
    except MetaApiError:
        await asyncio.sleep(1)
        result = await _call_complete()

    if not result.text.strip():
        await asyncio.sleep(1)
        try:
            result = await _call_complete()
        except RateLimitedError:
            raise
        except MetaApiError as exc:
            raise MetaApiError("Empty response from LLM") from exc

        if not result.text.strip():
            raise MetaApiError("Empty response from LLM")

    return AgentResult(
        text=result.text,
        used_search=False,
        rounds=1,
        note=None,
        elapsed_ms=result.elapsed_ms,
    )


def _extract_query(tool_call: Any) -> str:
    """Extract search query parameter from a tool call."""
    fn = getattr(tool_call, "function", None)
    if fn is not None:
        args_str = getattr(fn, "arguments", "")
    elif isinstance(tool_call, dict):
        args_str = tool_call.get("function", {}).get("arguments", "")
    else:
        args_str = ""

    if isinstance(args_str, dict):
        return str(args_str.get("query", "")).strip()

    try:
        data = json.loads(args_str)
        if isinstance(data, dict):
            return str(data.get("query", "")).strip()
    except Exception:
        pass
    return ""


def _extract_tool_call_id(tool_call: Any) -> str:
    """Extract tool call identifier with a safe fallback."""
    call_id = getattr(tool_call, "id", None)
    if not call_id and isinstance(tool_call, dict):
        call_id = tool_call.get("id")
    return str(call_id) if call_id else "call_1"


def _build_assistant_tool_message(tool_call: Any) -> dict[str, Any]:
    """Build serializable assistant message containing the tool call."""
    call_id = _extract_tool_call_id(tool_call)
    fn = getattr(tool_call, "function", None)
    if fn is not None:
        fn_name = getattr(fn, "name", "web_search")
        fn_args = getattr(fn, "arguments", "")
    elif isinstance(tool_call, dict):
        fn_dict = tool_call.get("function", {})
        fn_name = fn_dict.get("name", "web_search")
        fn_args = fn_dict.get("arguments", "")
    else:
        fn_name = "web_search"
        fn_args = ""

    if not isinstance(fn_args, str):
        fn_args = json.dumps(fn_args)

    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": fn_name,
                    "arguments": fn_args,
                },
            }
        ],
    }


async def _call_llm_with_retry(
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None,
) -> llm_service.LLMResult:
    """Invoke llm_service with tools and single retry on MetaApiError."""
    async def _invoke() -> llm_service.LLMResult:
        return await llm_service.complete_messages(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            reasoning_effort="minimal",
        )

    try:
        return await _invoke()
    except RateLimitedError:
        raise
    except MetaApiError:
        await asyncio.sleep(1)
        return await _invoke()


async def _agent_branch_impl(
    content: str, languages: Optional[str] = None
) -> AgentResult:
    """Internal implementation of the agent branch generative loop."""
    task, body = parse_agent_block(content)
    if not task.strip():
        raise InvalidRequestError(
            "Type what you want after @agent",
            status_code=422,
        )

    system_prompt = _load_prompt("agent_system.md")
    user_content = f"{task}\n{body}" if body.strip() else task

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    start_time = time.perf_counter()
    rounds = 0
    used_search = False
    note: Optional[str] = None
    text = ""

    while rounds < 2:
        if settings.AGENT_SEARCH_ENABLED:
            tools = [WEB_SEARCH_TOOL]
            tool_choice: Optional[Any] = "auto"
        else:
            tools = None
            tool_choice = None
        result = await _call_llm_with_retry(
            messages, tools=tools, tool_choice=tool_choice
        )
        rounds += 1

        tool_calls = result.tool_calls or []
        if tool_calls and settings.AGENT_SEARCH_ENABLED:
            used_search = True
            tool_call = tool_calls[0]
            query = _extract_query(tool_call)

            search_timeout = False
            search_results = ""
            try:
                search_results = await search_service.search(
                    query, timeout=8.0
                )
            except asyncio.TimeoutError:
                note = "search_timeout"
                search_timeout = True

            if search_timeout:
                break

            assistant_msg = _build_assistant_tool_message(tool_call)
            tool_msg = {
                "role": "tool",
                "tool_call_id": _extract_tool_call_id(tool_call),
                "content": search_results,
            }
            messages.append(assistant_msg)
            messages.append(tool_msg)
        else:
            text = result.text
            break

    if not text.strip():
        if settings.AGENT_SEARCH_ENABLED:
            forced_resp = await _call_llm_with_retry(
                messages, tools=None, tool_choice="none"
            )
        else:
            forced_resp = await _call_llm_with_retry(messages)
        text = forced_resp.text
        if not text.strip():
            raise MetaApiError("Empty response from LLM")

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    if OUT_OF_SCOPE_MARKER in text:
        return AgentResult(
            text=content,
            used_search=used_search,
            rounds=rounds,
            note="out_of_scope",
            elapsed_ms=elapsed_ms,
        )
    return AgentResult(
        text=text,
        used_search=used_search,
        rounds=rounds,
        note=note,
        elapsed_ms=elapsed_ms,
    )


async def agent_branch(
    content: str, languages: Optional[str] = None
) -> AgentResult:
    """Execute generative agent task with search tool loop and total timeout."""
    return await asyncio.wait_for(
        _agent_branch_impl(content, languages=languages),
        timeout=18.0,
    )
