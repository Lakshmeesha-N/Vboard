# VBoard

Privacy-first AI voice keyboard: Python FastAPI backend plus Kotlin Android app.

## Dependencies

Backend (`Vboard_backend/`, see `pyproject.toml`):

- `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
- `httpx` — Meta API calls and health checks
- `ddgs>=9.0.0` — DuckDuckGo search for the agent branch (`web_search` tool)
- `openai` — Meta/Spark chat-completions client
- `loguru`, `python-multipart`, `jiwer`
