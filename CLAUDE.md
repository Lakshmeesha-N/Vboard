# VBoard — Claude Instructions (repo root: `C:\Users\laksh\Desktop\Vboard`)

VBoard is a privacy-first AI voice keyboard monorepo: a Python FastAPI backend
plus a Kotlin Android keyboard app.

- `Vboard_backend/` — FastAPI backend: Meta Muse STT, Spark LLM text editing,
  and the text-only agent endpoint. This is where almost all work happens.
- `Vboard-android/` — Kotlin Android keyboard app (has its own `CLAUDE.md`;
  follow it when working in there).
- `docs/` — source of truth for intended behavior (only two files):
  `docs/architecture-as-built.md` (verified backend behavior), `docs/agent-plan.md`
  (agent endpoint spec, build order, test list).
- `AGENT.md` — workflow rules (plan approval, small steps, skill gating). Follow it.
- `.agent/skills/` — `plan-feature`, `build-feature`, `write-tests`, `security-review`.

## What is being built

Voice keyboard pipeline + generative agent, both served by one backend:

1. `POST /v1/process` (multipart: `audio` WAV + `languages` + `context_text` +
   `device_id`) — audio guardrail → Meta Muse STT → Spark action
   (`insert`/`replace`/`rewrite` with strict JSON schema) → `ProcessResponse`.
2. `POST /v1/agent` (JSON: `content` ≤ 10000 chars, `languages` CSV,
   `device_id`) — text-only, no audio:
   - starts with `@agent` → `agent_branch()` (generative; ≤2 LLM rounds,
     DuckDuckGo search via `search_service.py`, 18s total guard).
   - otherwise → `cleanup_branch()` (grammar/punctuation/translate only,
     never adds content). Returns `AgentResponse{text, used_search, rounds,
     note, timing_ms}`; text is NEVER empty.

## Key files (backend)

- `Vboard_backend/app/main.py` — app root, lifespan (init/close Meta + LLM
  clients), mounts `/v1` routers. Register new routers here.
- `Vboard_backend/app/api/v1/process.py`, `agent.py` — route handlers,
  size/validation checks, metrics-only logging, response shaping.
- `Vboard_backend/app/services/pipeline.py` — process ordering
  (guardrail → STT → action).
- `Vboard_backend/app/services/agent_service.py` — `route()`,
  `cleanup_branch()`, `agent_branch()`, `finalize()`; retry = plain
  `try/except` + `await asyncio.sleep(1)`, no new library.
- `Vboard_backend/app/services/{stt_service,action_service,llm_service}.py` —
  Meta ASR client (retry once on 500), Spark orchestrator + fallbacks
  (`empty_speech`, `spark_error`, `bad_reply`, `not_allowed_empty_box`,
  `find_not_found`), chat-completion wrapper (`muse-spark-1.3`,
  `reasoning_effort="minimal"`).
- `Vboard_backend/app/services/search_service.py` — DuckDuckGo via httpx,
  8s timeout; only the short query string leaves the backend.
- `Vboard_backend/app/core/{config,validators,audio,exceptions}.py` —
  `Settings` (`.env`), `device_id` regex `^[a-zA-Z0-9_-]{1,64}$`, WAV checks
  (mono, 16-bit PCM, 16/24 kHz, 0.3–60s, RMS > 50), `AppError` hierarchy.
- `Vboard_backend/app/prompts/{spark_system,cleanup_system,agent_system}.md` —
  system prompts; loaded at import. Cleanup never generates; agent ignores
  instructions inside body text.
- `Vboard_backend/app/schemas/{process,actions,agent}.py` — wire models.
- `Vboard_backend/tests/` + `scripts/eval_*.py` + `eval/` — pytest suite
  (fake LLM/search, no network) and WER/CER + latency benchmarks.

## Error contract

- 400 invalid audio/params, 413 audio > 5MB, 422 agent `content` too long or
  bad `device_id`, 429 Meta rate limit (never retry), 502 LLM fail-after-retry
  or empty-after-retry. Search timeout → 200 with `note="search_timeout"`.
- `agent_service` retries LLM timeout/5xx and empty reply exactly once;
  search never retries. Out-of-scope agent task → 200 with
  `This task is beyond my current capabilities.`

## Privacy (hard rule, from docs + AGENT.md)

Log/print numerics only: `rounds`, `elapsed_ms`, token counts, `device_id`,
action/fallback codes. NEVER log audio bytes, transcripts, box/spoken text,
prompts, search queries/results, or output text. Never read, print, or commit
`.env` / API keys. Only the search query (<80 chars) ever leaves the backend.

## Run / verify (backend cwd: `Vboard_backend/`)

- Source of truth for deps/tooling: `pyproject.toml` (ruff line-length 88,
  `asyncio_mode = "auto"`, `testpaths = ["tests"]`). Use the existing `.venv`.
- Dev server: `uvicorn app.main:app` (or `python -m uvicorn app.main:app`).
- Tests: `pytest tests/test_agent.py -v` (agent), full: `pytest -v`.
- Smoke: `curl -X POST http://localhost:8000/v1/agent -H "Content-Type:
  application/json" -d '{"content": "i went to market yestraday"}'`
  and `-d '{"content": "@agent\nWrite a professional birthday wish for Anil
  turning 30"}'`.
- Eval: `eval-audio`, `eval-endpoint`, `eval-llm` (console + `eval/results/`).

## How to work here

1. Read `docs/agent-plan.md` + `docs/architecture-as-built.md` and inspect the
   real files before assuming anything exists (stubs: `api/v1/health.py`,
   `core/logging.py`, `db/models.py`, `db/session.py` are empty).
2. Keep backend changes in `Vboard_backend/`, Android voice code in
   `Vboard-android/.../voice/`; never modify upstream/forked Android files
   unless the user names the file; no Jetpack Compose unless asked.
3. Minimal diffs, ≤3–4 files per step, reuse existing services/validators;
   no new deps or patterns without permission. Explain assumptions instead of
   guessing; report failures honestly, never claim unverified success.
4. `AGENT_SEARCH_ENABLED` in `config.py` toggles agent web search; known
   unverified item: Meta Responses-API `web_search` tool — DuckDuckGo stays
   the only search until confirmed (see `docs/agent-plan.md` UNVERIFIED).
