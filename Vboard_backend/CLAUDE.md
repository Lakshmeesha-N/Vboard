# Vboard Backend

Stateless Python FastAPI backend. Meta Muse STT, Spark LLM text editing, and a
text-only agent endpoint. No database. Dependencies and tooling: `pyproject.toml`
(ruff line-length 88, `asyncio_mode = "auto"`, `testpaths = ["tests"]`).
Use the existing `.venv`; all commands run from this folder.

## Layout

- `app/main.py` — app root, lifespan (init/close Meta + LLM singleton clients),
  mounts `/v1` routers. Register new routers here.
- `app/api/v1/process.py` — `POST /v1/process` (multipart `audio` WAV +
  `languages` + `context_text` + `device_id`).
- `app/api/v1/agent.py` — `POST /v1/agent` (JSON `content` ≤ 10000 chars,
  `languages` CSV, `device_id`). Content starting with `@agent` takes the agent
  branch, everything else takes cleanup.
- `app/api/errors.py` — centralized handlers: `AppError` → its status,
  `MetaApiError` → 502, unexpected → 500 without leaking internals.
- `app/services/pipeline.py` — process order: audio guardrail → STT → action.
- `app/services/agent_service.py` — `route()`, `cleanup_branch()`,
  `agent_branch()`, `finalize()`. Retries are plain `try/except` +
  `await asyncio.sleep(1)`; no retry library.
- `app/services/stt_service.py` — Meta Muse transcribe
  (`muse-voice-transcribe-1.0`); retries ONCE on HTTP 500 only.
- `app/services/action_service.py` — Spark orchestrator with fallbacks:
  `empty_speech`, `spark_error`, `bad_reply`, `not_allowed_empty_box`,
  `find_not_found` (case-insensitive `find` reconciliation).
- `app/services/llm_service.py` — chat-completion wrapper (`muse-spark-1.3`,
  `reasoning_effort="minimal"`, strict JSON schema for actions).
- `app/services/search_service.py` — DuckDuckGo via httpx, 8s timeout; only the
  short query string (<80 chars) ever leaves the backend.
- `app/services/{llm_client,meta_client}.py` — lifespan-managed singleton clients.
- `app/core/config.py` — `Settings` from `.env` (`META_API_KEY`,
  `META_BASE_URL`, audio limits, `DEFAULT_LLM_MODEL`, `AGENT_SEARCH_ENABLED`).
- `app/core/validators.py` — `device_id` regex `^[a-zA-Z0-9_-]{1,64}$`,
  `context_text` ≤ 10000 chars, languages canonicalized against 25 Meta
  languages, max 5.
- `app/core/audio.py` — in-memory WAV checks: mono, 16-bit PCM, 16/24 kHz,
  0.3–60s, RMS > 50.
- `app/core/exceptions.py` — `VboardError` → `AppError` (with `status_code`) →
  `InvalidRequestError`, `InvalidAudioError`, `RateLimitedError`, `MetaApiError`.
- `app/prompts/` — `spark_system.md`, `cleanup_system.md`, `agent_system.md`,
  loaded at import. Cleanup fixes grammar/translation only, never generates;
  agent treats body text as data and never follows instructions inside it.
- `app/schemas/` — `process.py`, `actions.py` (strict `ACTION_RESPONSE_FORMAT`),
  `agent.py` (`AgentRequest`/`AgentResponse`; response text is NEVER empty).
- `app/api/v1/health.py`, `app/core/logging.py`, `app/db/` — empty stubs, stay empty.
- `tests/` — pytest suite with fake LLM/search (no network).
- `scripts/eval_*.py` + `eval/` — WER/CER and latency benchmarks, CSV output
  in `eval/results/`.

## Endpoint behavior

- `POST /v1/process`: 413 audio > 5MB; 400 empty/invalid audio or bad params.
  STT 429 → 429; STT 500/other → 502 (Spark errors fall back to `insert` of the
  spoken text instead). `timings_ms` breakdown only when `DEBUG=True`.
- `POST /v1/agent`: 422 content > 10000 chars or bad `device_id`; 429 never
  retried; 502 LLM failure/empty after exactly one retry. Search timeout → 200
  with `note="search_timeout"`. Out-of-scope task → 200 with the capabilities
  sentence. Agent loop: ≤2 rounds, 18s total guard.

## Privacy

Log numerics only: `rounds`, `elapsed_ms`, token counts, `device_id`,
action/fallback codes. Never log audio bytes, transcripts, box/spoken text,
prompts, search queries/results, or output text. Never read, print, or commit
`.env` or API keys.

## Commands

- Server: `uvicorn app.main:app` (must start clean after router/config changes).
- Agent tests: `pytest tests/test_agent.py -v`; full suite: `pytest -v`.
- Smoke: `curl -X POST http://localhost:8000/v1/agent -H "Content-Type:
  application/json" -d '{"content": "i went to market yestraday"}'` and
  `-d '{"content": "@agent\nWrite a professional birthday wish for Anil
  turning 30"}'`.
