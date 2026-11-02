# Vboard Backend

Stateless FastAPI backend for VBoard — Meta Muse speech-to-text, Spark LLM text editing, and the text-only agent endpoint. No database.

> Root overview: [`../README.md`](../README.md) · Verified behavior: [`../docs/architecture-as-built.md`](../docs/architecture-as-built.md) · Agent spec: `docs/agent-plan.md` (local-only, gitignored)

---

## What it does

| Endpoint | Input | Pipeline |
|---|---|---|
| `POST /v1/process` | multipart `audio` (WAV) + `languages` + `context_text` + `device_id` | Audio guardrail → Muse STT (`muse-voice-transcribe-1.0`) → Spark action (`muse-spark-1.3`, strict JSON `insert`/`replace`/`rewrite`) |
| `POST /v1/agent` | JSON `{content ≤ 10000 chars, languages?, device_id?}` — no audio | `@agent…` → generative branch (≤2 LLM rounds, DuckDuckGo search, 18s guard) · otherwise cleanup branch (grammar/punctuation/translate only, never adds content) |

**Key files**

- `app/main.py` — lifespan (init/close Meta + LLM singleton clients), mounts `/v1` routers. Register new routers here.
- `app/api/v1/process.py`, `agent.py` — route handlers, size/validation checks, metrics-only logging, response shaping.
- `app/services/pipeline.py` — process order: guardrail → STT → action.
- `app/services/agent_service.py` — `route()`, `cleanup_branch()`, `agent_branch()`, `finalize()`. Retry = plain `try/except` + `await asyncio.sleep(1)`, no library.
- `app/services/{stt_service,action_service,llm_service}.py` — Meta ASR client (retry once on 500), Spark orchestrator + fallbacks (`empty_speech`, `spark_error`, `bad_reply`, `not_allowed_empty_box`, `find_not_found`), chat-completion wrapper (`reasoning_effort="minimal"`).
- `app/services/search_service.py` — DuckDuckGo via httpx, 8s timeout. Only the short query string ever leaves the backend.
- `app/core/{config,validators,audio,exceptions}.py` — `Settings` from `.env`, `device_id` regex `^[a-zA-Z0-9_-]{1,64}$`, WAV checks (mono, 16-bit PCM, 16/24 kHz, 0.3–60s, RMS > 50), `AppError` hierarchy.
- `app/prompts/{spark_system,cleanup_system,agent_system}.md` — system prompts, loaded at import.
- `app/schemas/{process,actions,agent}.py` — wire models. Agent response text is NEVER empty.
- `app/api/v1/health.py`, `app/core/logging.py`, `app/db/` — empty stubs, stay empty.

---

## Setup

```bash
cd Vboard_backend
# use the existing .venv — source of truth for deps/tooling: pyproject.toml
pip install -e .                    # enables short commands below (eval-audio, …)
cp .env.example .env                # then set META_API_KEY (never commit .env)
python -m uvicorn app.main:app      # dev server → http://127.0.0.1:8000
```

**Smoke test**

```bash
curl -X POST http://localhost:8000/v1/agent -H "Content-Type: application/json" \
  -d '{"content": "i went to market yestraday and buyed some vegitables"}'
# → corrected text, used_search=false, rounds=1

curl -X POST http://localhost:8000/v1/agent -H "Content-Type: application/json" \
  -d '{"content": "@agent\nWrite a professional birthday wish for Anil turning 30"}'
# → birthday wish text, rounds >= 1
```

**Tests**

```bash
pytest tests/test_agent.py -v   # agent suite (fake LLM/search, no network)
pytest -v                       # full suite
```

---

## Scripts & commands

Source: `pyproject.toml` (`[project.scripts]`) + `scripts/`. Run from `Vboard_backend/` with the `.venv` active. Short commands work after `pip install -e .`; otherwise use the `python -m` fallback.

| Script | Short command | No-shortcut fallback |
|---|---|---|
| `scripts/eval_audio.py` | `eval-audio [--lang Kannada,English] [--only kannada_1] [--show]` | `python -m scripts.eval_audio [--lang ...] [--only ...] [--show]` |
| `scripts/eval_endpoint.py` | `eval-endpoint [--url http://127.0.0.1:8000/v1/process] [--dir eval/audio] [--lang Kannada,English] [--only english_1] [--runs 1]` | `python -m scripts.eval_endpoint [--url ...] [--dir ...] [--lang ...] [--only ...] [--runs ...]` |
| `scripts/eval_llm.py` | `eval-llm [--csv eval/texttest.csv] [--only 5] [--runs 1] [--reasoning-effort minimal] [--show]` | `python -m scripts.eval_llm [--csv ...] [--only ...] [--runs ...] [--show]` |
| `scripts/voice_test.py` | `voice-test [--url http://127.0.0.1:8000] [--rate 24000] [--lang Kannada] [--key ctrl_r]` | `python -m scripts.voice_test [--url ...] [--rate ...] [--lang ...] [--key ...]` |

### What each script does

- **eval-audio** — Meta Muse STT accuracy (WER/CER via JiWER) + latency over clips in `eval/metadata.csv`. Writes timestamped CSV to `eval/results/`. Needs `.env` credentials. No server required.
  - `--lang` — comma-separated language bias hints (e.g. `Kannada,English`).
  - `--only` — run only clips whose `file_path` contains this string (e.g. `kannada_1`).
  - `--show` — print reference + transcript under each clip.
- **eval-endpoint** — Hits a **running** server's `POST /v1/process` with WAV files, checks guardrails, reports latency/cost. Writes summary CSV to `eval/results/`. Server must be up (`python -m uvicorn app.main:app`).
  - `--url` (default `http://127.0.0.1:8000/v1/process`) · `--dir` (default `eval/audio`) · `--lang` (e.g. `Kannada,English`) · `--only` (filename substring) · `--runs` (default `1`).
- **eval-llm** — Benchmarks the Spark editing action (`insert`/`replace`/`rewrite`) against `eval/texttest.csv` expected action + text. Reports pass rate, CER, token cost to `eval/results/`. Needs `.env` credentials. No server required.
  - `--csv` (default `eval/texttest.csv`) · `--only` (row id, e.g. `5`) · `--runs` (default `1`) · `--reasoning-effort` (`minimal|low|medium|high|xhigh|max`, overrides `SPARK_REASONING_EFFORT`) · `--show` (print Spark text for failed rows).
- **voice-test** — Laptop mic tester for the full pipeline: hold hotkey, speak, release to POST to `/v1/process`. Prints transcript + action + box text. Needs mic + `pip install -e ".[devtools]"` (`sounddevice`, `pynput`) and a running server.
  - `--url` (default `http://127.0.0.1:8000`) · `--rate` (`24000` default or `16000`) · `--lang` (repeatable: `--lang Kannada --lang English`) · `--key` (default `ctrl_r`; modifiers/combos only: `ctrl_r`, `shift_r`, `ctrl+shift`, `scroll_lock`, `pause` — never letter/function keys).

### voice-test interactive controls

Only **voice-test** is interactive. The 3 eval scripts just run and exit — no keys or slash commands.

```bash
voice-test
# or: python -m scripts.voice_test --key ctrl_r --rate 24000 --lang Kannada
```

1. **Push-to-talk** (default: hold Right-Ctrl): hold → `[Recording started...]`, speak, release → auto-sends to `POST /v1/process`. Too short (< 0.3s) → ignored; too long → capped at 30s. Change at launch with `--key`.
2. **Slash commands** (type into the same terminal while it runs):

| Type this | What it does |
|---|---|
| `/show` | Print current box text (becomes `context_text` for the next voice turn). |
| `/undo` | Undo last change, restore previous box. Empty stack → `[Undo stack is empty]`. |
| `/clear` | Empty the box and clear undo history. |
| `/box <text>` | Manually set box text (saved to undo stack). |
| `/quit` | Exit (`Ctrl+C` / `Ctrl+D` also work). |

Anything else prints: `[Unknown command: ... Available: /undo, /clear, /show, /box <text>, /quit]`.

### Eval inputs & outputs

- `eval/metadata.csv` (`file_path,language,transcript`) + `eval/audio/` clips → `eval-audio` (gitignored samples/results).
- `eval/texttest.csv` (`id,mix,box_text,spoken_text,expected_action,expected_find,expected_which,expected_text,notes`) → `eval-llm`.
- `eval/download_samples.py` — pulls Kannada/Hindi/English clips from Hugging Face into `eval/audio/` + `metadata.csv` (needs `HF_TOKEN`, eval extra: `pip install -e ".[eval]"`).
- All eval writes go to `eval/results/` (`endpoint_*.csv`, `llm_*.csv`, `run_*.csv`) — gitignored.

---

## Error contract

| Condition | Status |
|---|---|
| audio > 5 MB | `413` |
| empty/invalid audio, bad params | `400` |
| agent `content` > 10000 chars, bad `device_id` | `422` |
| Meta rate limit | `429` (never retried) |
| LLM fail/empty after exactly one retry | `502` |
| search timeout | `200` with `note="search_timeout"` |
| out-of-scope agent task | `200` with the capabilities sentence |

`timings_ms` breakdown only when `DEBUG=True`. Agent loop: ≤2 rounds, 18s total guard; search never retried.

---

## Privacy (hard rule)

Log numerics only: `rounds`, `elapsed_ms`, token counts, `device_id`, action/fallback codes. Never log audio bytes, transcripts, box/spoken text, prompts, search queries/results, or output text. Never read, print, or commit `.env` / API keys. Only the search query (<80 chars) ever leaves the backend.

---

## Config

`app/core/config.py` (`Settings`, from `.env`): `META_API_KEY`, `META_BASE_URL`, audio limits (`MAX_AUDIO_BYTES`, `MIN/MAX_AUDIO_DURATION_S`, `SILENCE_RMS_THRESHOLD`), `DEFAULT_LLM_MODEL` (`muse-spark-1.3`), `SPARK_REASONING_EFFORT` (`minimal`), `AGENT_SEARCH_ENABLED`. Toggles: `DEBUG` (timings exposure), `AGENT_SEARCH_ENABLED` (agent web search).
