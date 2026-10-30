# Architecture As-Built: Vboard Backend

This document details the actual, verified implementation of `Vboard_backend` derived directly from inspecting the codebase.

---

## 1. Folder Map

### `app/`
- [`app/main.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/main.py): FastAPI application root defining lifespan context manager (initializing/closing HTTP clients), registering global exception handlers, and mounting `/v1` routers.
- [`app/api/errors.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/api/errors.py): Centralized FastAPI exception handlers mapping `AppError`, `MetaApiError`, and generic `Exception` to standardized JSON responses without leaking internals.
- [`app/api/v1/health.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/api/v1/health.py): Empty file (stubbed health check module; no routes defined).
- [`app/api/v1/process.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/api/v1/process.py): FastAPI route handler for `POST /v1/process` orchestrating request extraction, size/payload validation, pipeline execution, metrics logging, and response formatting.
- [`app/core/audio.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/audio.py): In-memory WAV audio validation routines checking container headers (16-bit PCM, mono, 16/24 kHz), exact frame duration (0.3s–60s), and subsampled RMS silence threshold without writing to disk.
- [`app/core/config.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/config.py): Pydantic `BaseSettings` defining application, API credentials, audio limits, and LLM defaults loaded from `.env` and environment variables.
- [`app/core/exceptions.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/exceptions.py): Class hierarchy of application exceptions (`VboardError`, `AppError`, `InvalidRequestError`, `InvalidAudioError`, `RateLimitedError`, `MetaApiError`).
- [`app/core/logging.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/logging.py): Empty file (logger configuration is handled via default Loguru setup).
- [`app/core/validators.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/validators.py): Request input validation functions for `device_id` regex pattern, `context_text` length limit, and canonicalization of comma-separated language hints against Meta's supported list.
- [`app/db/models.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/db/models.py): Empty file (stateless backend; no database models defined).
- [`app/db/session.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/db/session.py): Empty file (stateless backend; no database session defined).
- [`app/prompts/__init__.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/prompts/__init__.py): Exposes `SPARK_SYSTEM_PROMPT` read directly at import time from `spark_system.md`.
- [`app/prompts/spark_system.md`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/prompts/spark_system.md): System prompt markdown instructions instructing Spark on voice keyboard editing rules, tag conventions (`<box>`, `<spoken>`), action schemas, and few-shot examples.
- [`app/schemas/actions.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/schemas/actions.py): Pydantic `Action` model, `parse_action()` parsing/validation helper, and dynamically built strict `ACTION_RESPONSE_FORMAT` schema.
- [`app/schemas/process.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/schemas/process.py): Pydantic request and response models for the HTTP API (`ActionModel`, `ProcessResponse`).
- [`app/services/action_service.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/action_service.py): Spark LLM invocation orchestrator handling tag stripping, prompt construction, client completion call, fallbacks (`empty_speech`, `spark_error`, `bad_reply`, `not_allowed_empty_box`, `find_not_found`), and case-insensitive replace reconciliation.
- [`app/services/llm_client.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/llm_client.py): Lifecycle management (init, get, close) for the shared singleton `AsyncOpenAI` client targeting Meta/Spark endpoints.
- [`app/services/llm_service.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/llm_service.py): Chat completion wrapper around `AsyncOpenAI` handling execution timing, token usage extraction (prompt, completion, cached, reasoning), error translation, and privacy-preserving numeric logging.
- [`app/services/meta_client.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/meta_client.py): Lifecycle management (init, get, close) for the shared singleton `httpx.AsyncClient` targeting Meta ASR endpoints.
- [`app/services/pipeline.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/pipeline.py): End-to-end processing pipeline orchestrating sequential execution of Audio Guardrail -> Muse STT -> Spark Action Service and aggregating stage latency timings.
- [`app/services/stt_service.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/stt_service.py): Meta Muse Voice Transcribe client sending multipart WAV audio and JSON metadata, featuring single-retry on HTTP 500 and translation into `TranscriptionResult`.

### `scripts/`
- [`scripts/__init__.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/scripts/__init__.py): Empty package initializer.
- [`scripts/eval_audio.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/scripts/eval_audio.py): Benchmark script evaluating Meta Muse ASR accuracy (WER/CER via JiWER) on audio clips listed in `eval/metadata.csv`.
- [`scripts/eval_endpoint.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/scripts/eval_endpoint.py): End-to-end integration benchmark script submitting test WAV files to `POST /v1/process`, checking guardrails, measuring server latencies, calculating costs, and exporting CSV summaries.
- [`scripts/eval_llm.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/scripts/eval_llm.py): Benchmark script evaluating Spark LLM editing actions against expected actions and text targets defined in `eval/texttest.csv`.

### `eval/`
- [`eval/download_samples.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/eval/download_samples.py): Dataset downloader script pulling Kannada, Hindi, and English audio samples from Hugging Face (`ai4bharat/IndicVoices`, `openslr/librispeech_asr`) into `eval/audio/` and populating `metadata.csv`.
- [`eval/metadata.csv`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/eval/metadata.csv): Metadata catalog for audio evaluation clips (`file_path,language,transcript`).
- [`eval/texttest.csv`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/eval/texttest.csv): Test dataset for LLM action evaluation (`id,mix,box_text,spoken_text,expected_action,expected_find,expected_which,expected_text,notes`).
- `eval/audio/`: Directory containing test WAV audio files (`english_1..5.wav`, `hindi_1..5.wav`, `kannada_1..5.wav`).
- `eval/results/`: Directory holding timestamped CSV evaluation runs (`endpoint_*.csv`, `llm_*.csv`, `run_*.csv`).

---

## 2. Request Flow for `POST /v1/process`

```
Client (Multipart Form)
  │ audio: UploadFile (WAV)
  │ languages: Optional[str]
  │ context_text: Optional[str]
  │ device_id: Optional[str]
  ▼
app/api/v1/process.py : process_audio()
  ├─ 1. Read Upload: await audio.read(MAX_AUDIO_BYTES + 1)
  │    └─ len > MAX_AUDIO_BYTES (5MB) -> raise HTTPException(413)
  │    └─ len == 0                     -> raise HTTPException(400)
  ├─ 2. Input Validation:
  │    ├─ validate_device_id(device_id)    [app/core/validators.py] -> regex check; invalid -> raise InvalidRequestError(400)
  │    ├─ validate_context_text(ctx)       [app/core/validators.py] -> len <= 10000; invalid -> raise InvalidRequestError(400)
  │    └─ parse_languages(languages)       [app/core/validators.py] -> canonicalize against 25 Meta langs, drop invalid, slice <= 5
  ▼
app/services/pipeline.py : run()
  ├─ 3. Audio Guardrail: validate_wav_bytes() [app/core/audio.py]
  │    ├─ wave.open() container check: mono, 16-bit PCM, 16000Hz or 24000Hz
  │    ├─ actual duration check: 0.3s <= duration <= 60.0s
  │    ├─ subsampled RMS check: rms > SILENCE_RMS_THRESHOLD (50.0)
  │    └─ Failure at any check -> raise InvalidAudioError(400 or 413)
  │
  ├─ 4. Speech-to-Text: stt_service.transcribe() [app/services/stt_service.py]
  │    ├─ POST /asr/transcribe via httpx.AsyncClient (Meta)
  │    ├─ Payload: mode="PUSH_TO_TALK", model="muse-voice-transcribe-1.0", audioEncoding="WAV", optional languageBias
  │    ├─ If status == 500: sleep 0.3s and retry ONCE
  │    ├─ If status == 200: parse JSON -> transcript, audioDurationMs
  │    └─ If error: 400/413 -> InvalidAudioError(400); 429 -> RateLimitedError(429); 500/other -> MetaApiError(502)
  │
  ├─ 5. Action Processing: action_service.process() [app/services/action_service.py]
  │    ├─ If spoken_text is empty/whitespace:
  │    │    └─ Returns ActionResult(action=None, used_fallback=False, fallback_reason="empty_speech")
  │    ├─ Strip literal tags: clean_text(box_text), clean_text(spoken_text)
  │    ├─ Build user message: "<box>{box}</box>\n<spoken>{spoken}</spoken>"
  │    ├─ Invoke Spark: llm_service.complete() [app/services/llm_service.py]
  │    │    ├─ System prompt: SPARK_SYSTEM_PROMPT
  │    │    ├─ response_format: ACTION_RESPONSE_FORMAT (strict JSON schema)
  │    │    ├─ reasoning_effort: settings.SPARK_REASONING_EFFORT ("minimal")
  │    │    └─ On RateLimitedError/MetaApiError: fallback -> Action(insert, text=spoken_text), fallback_reason="spark_error"
  │    ├─ Parse Spark reply: parse_action(reply.text) [app/schemas/actions.py]
  │    │    └─ If parsing/validation fails: fallback -> Action(insert, text=spoken_text), fallback_reason="bad_reply"
  │    ├─ Empty box guard:
  │    │    └─ If not box_text.strip() and action in ("replace", "rewrite"):
  │    │         fallback -> Action(insert, text=spoken_text), fallback_reason="not_allowed_empty_box"
  │    └─ Replace reconciliation:
  │         ├─ If parsed.find in box_text: keep action
  │         ├─ Else if re.search(find, box_text, IGNORECASE): update parsed.find to exact box casing
  │         └─ Else (not found in box): action=None, used_fallback=True, fallback_reason="find_not_found"
  ▼
app/api/v1/process.py : finalize response
  ├─ 6. Privacy Logging:
  │    └─ Logs device_id, timing breakdowns (read, guardrail, stt, spark, total), token counts, action_type, fallback flags.
  │    └─ NEVER logs audio bytes, spoken words, box content, or transcripts.
  ├─ 7. DEBUG Flag Behavior:
  │    ├─ If settings.DEBUG is True: response.timings_ms contains detailed dictionary {"read_ms", "guardrail_ms", "stt_ms", "spark_ms", "total_ms"}.
  │    └─ If settings.DEBUG is False: response.timings_ms is None (null in JSON).
  └─ 8. Return ProcessResponse Model
```

---

## 3. Data Types

| Class Name | File | Kind | Fields (Type & Default) | Instantiated By | Consumed By |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Settings`** | `app/core/config.py` | Pydantic `BaseSettings` | `APP_NAME: str = "Vboard Backend"`<br>`ENVIRONMENT: str = "development"`<br>`DEBUG: bool = True`<br>`PORT: int = 8000`<br>`HOST: str = "0.0.0.0"`<br>`META_API_KEY: Optional[str] = None`<br>`META_BASE_URL: Optional[str] = "https://api.meta.ai/v1"`<br>`HF_TOKEN: Optional[str] = None`<br>`DEFAULT_VOICE_MODEL: str = "muse-voice-transcribe-1.0"`<br>`MAX_AUDIO_BYTES: int = 5242880`<br>`MIN_AUDIO_DURATION_S: float = 0.3`<br>`MAX_AUDIO_DURATION_S: float = 60.0`<br>`SILENCE_RMS_THRESHOLD: float = 50.0`<br>`MAX_CONTEXT_TEXT_LENGTH: int = 10000`<br>`MAX_LANGUAGES_COUNT: int = 5`<br>`DEFAULT_LLM_MODEL: str = "muse-spark-1.3"`<br>`SPARK_REASONING_EFFORT: str = "minimal"`<br>`SARVAM_API_KEY: Optional[str] = None`<br>`GEMINI_API_KEY: Optional[str] = None`<br>`GROQ_API_KEY: Optional[str] = None` | Module import in `app/core/config.py` as singleton `settings` | Throughout application services, validators, and endpoints |
| **`VboardError`** | `app/core/exceptions.py` | Python Exception | Base class (inherits `Exception`) | Base class | Subclasses |
| **`AppError`** | `app/core/exceptions.py` | Python Exception | `message: str = "Application error"`<br>`status_code: int = 400` | Base class | Handled by `app/api/errors.py` |
| **`InvalidRequestError`** | `app/core/exceptions.py` | Python Exception | `message: str = "Invalid request parameter"`<br>`status_code: int = 400` | `app/core/validators.py` | Handled by `app/api/errors.py` (returns HTTP 400) |
| **`InvalidAudioError`** | `app/core/exceptions.py` | Python Exception | `message: str = "Invalid or unsupported audio payload"`<br>`status_code: int = 400` | `app/core/audio.py`, `app/services/stt_service.py` | Handled by `app/api/errors.py` (returns HTTP 400 or 413) |
| **`RateLimitedError`** | `app/core/exceptions.py` | Python Exception | `message: str = "Meta API rate limit exceeded"`<br>`status_code: int = 429` | `app/services/stt_service.py`, `app/services/llm_service.py` | `action_service.py` (triggers fallback); `app/api/errors.py` (returns HTTP 429) |
| **`MetaApiError`** | `app/core/exceptions.py` | Python Exception | `message: str = "Meta API request failed"`<br>`status_code: int \| None = None` | `app/services/stt_service.py`, `app/services/llm_service.py` | `action_service.py` (triggers fallback); `app/api/errors.py` (returns HTTP 502) |
| **`AudioValidationResult`** | `app/core/audio.py` | Frozen Dataclass | `channels: int`<br>`sample_rate: int`<br>`sample_width: int`<br>`duration_s: float`<br>`rms: float` | `app/core/audio.py:validate_wav_bytes()` | Returned to caller (verified in unit tests) |
| **`Action`** | `app/schemas/actions.py` | Pydantic `BaseModel` | `action: Literal["insert", "replace", "rewrite"]`<br>`text: str`<br>`find: str`<br>`which: Literal["first", "last", "all"] = "last"` | `app/schemas/actions.py:parse_action()`, `action_service.py` | `action_service.py`, `pipeline.py`, `process.py`, tests |
| **`ActionModel`** | `app/schemas/process.py` | Pydantic `BaseModel` | `action: str`<br>`text: str`<br>`find: Optional[str] = None`<br>`which: Optional[str] = None` | `app/api/v1/process.py` | `ProcessResponse` |
| **`ProcessResponse`** | `app/schemas/process.py` | Pydantic `BaseModel` | `transcript: str`<br>`timing_ms: float`<br>`audio_duration_ms: int`<br>`action: Optional[ActionModel] = None`<br>`used_fallback: bool = False`<br>`note: Optional[str] = None`<br>`timings_ms: Optional[dict[str, float]] = None` | `app/api/v1/process.py` | FastAPI response serializer to client JSON |
| **`ActionResult`** | `app/services/action_service.py` | Frozen Dataclass | `action: Optional[Action]`<br>`used_fallback: bool`<br>`fallback_reason: Optional[str]`<br>`elapsed_ms: float`<br>`prompt_tokens: int`<br>`completion_tokens: int`<br>`cached_tokens: int`<br>`reasoning_tokens: int` | `app/services/action_service.py:process()` | `app/services/pipeline.py` |
| **`LLMResult`** | `app/services/llm_service.py` | Frozen Dataclass | `text: str`<br>`elapsed_ms: float`<br>`prompt_tokens: int`<br>`completion_tokens: int`<br>`cached_tokens: int`<br>`reasoning_tokens: int` | `app/services/llm_service.py:complete()` | `app/services/action_service.py` |
| **`PipelineResult`** | `app/services/pipeline.py` | Frozen Dataclass | `transcript: str`<br>`audio_duration_ms: int`<br>`timings_ms: dict[str, float]`<br>`action: Optional[Action]`<br>`used_fallback: bool`<br>`fallback_reason: Optional[str]`<br>`prompt_tokens: int = 0`<br>`completion_tokens: int = 0`<br>`cached_tokens: int = 0`<br>`reasoning_tokens: int = 0` | `app/services/pipeline.py:run()` | `app/api/v1/process.py` |
| **`TranscriptionResult`** | `app/services/stt_service.py` | Frozen Dataclass | `transcript: str`<br>`elapsed_ms: float`<br>`audio_duration_ms: int` | `app/services/stt_service.py:transcribe()` | `app/services/pipeline.py` |

---

## 4. Validation

| Target | File & Function | Rule | Error or Fallback Triggered |
| :--- | :--- | :--- | :--- |
| **Upload Size** | `app/api/v1/process.py:process_audio` | Streamed read buffer `len(wav_bytes) > MAX_AUDIO_BYTES` (5 MB) | `HTTPException(413, "Audio payload exceeds maximum size limit of 5 MB")` |
| **Empty Upload** | `app/api/v1/process.py:process_audio` | `not wav_bytes` | `HTTPException(400, "Audio payload is empty")` |
| **Device ID** | `app/core/validators.py:validate_device_id` | Must match regex `^[a-zA-Z0-9_-]{1,64}$` | `InvalidRequestError` -> HTTP 400 |
| **Context Text** | `app/core/validators.py:validate_context_text` | Length must be `<= MAX_CONTEXT_TEXT_LENGTH` (10,000 chars) | `InvalidRequestError` -> HTTP 400 |
| **Languages** | `app/core/validators.py:parse_languages` | Case-insensitive match against 25 Meta languages; unrecognised dropped; max 5 | Silently filters out invalid; returns `None` if empty |
| **Audio Container** | `app/core/audio.py:validate_wav_bytes` | Must be readable as standard WAV | `InvalidAudioError("Invalid WAV audio format")` -> HTTP 400 |
| **Audio Channels** | `app/core/audio.py:validate_wav_bytes` | Channels must equal `1` (mono) | `InvalidAudioError("Audio must be mono...")` -> HTTP 400 |
| **Audio Bit Depth** | `app/core/audio.py:validate_wav_bytes` | Sample width must equal `2` bytes (16-bit PCM) | `InvalidAudioError("Audio must be 16-bit PCM...")` -> HTTP 400 |
| **Audio Sample Rate** | `app/core/audio.py:validate_wav_bytes` | Sample rate must be `16000` or `24000` Hz | `InvalidAudioError("Sample rate must be 16000Hz or 24000Hz...")` -> HTTP 400 |
| **Audio Frames** | `app/core/audio.py:validate_wav_bytes` | Frame count must be `> 0` | `InvalidAudioError("Audio payload contains no audio frames")` -> HTTP 400 |
| **Min Audio Duration**| `app/core/audio.py:validate_wav_bytes` | Actual frame duration `>= MIN_AUDIO_DURATION_S` (0.3s) | `InvalidAudioError("Audio duration ... less than minimum 0.3s")` -> HTTP 400 |
| **Max Audio Duration**| `app/core/audio.py:validate_wav_bytes` | Actual frame duration `<= MAX_AUDIO_DURATION_S` (60.0s) | `InvalidAudioError("Audio duration ... exceeds maximum 60.0s")` -> HTTP 400 |
| **Silence / RMS** | `app/core/audio.py:validate_wav_bytes` | Subsampled 16-bit RMS must be `> SILENCE_RMS_THRESHOLD` (50.0) | `InvalidAudioError("Audio is completely silent")` -> HTTP 400 |
| **Speech Text** | `app/services/action_service.py:process` | `not spoken_text or not spoken_text.strip()` | No LLM call; returns `ActionResult(action=None, fallback_reason="empty_speech")` |
| **Spark JSON Reply** | `app/schemas/actions.py:parse_action` | Must be valid JSON object, markdown fences stripped | Fallback -> `Action(insert, spoken_text)`, `fallback_reason="bad_reply"` |
| **Action Field** | `app/schemas/actions.py:Action` | `action` in `("insert", "replace", "rewrite")` | Fallback -> `Action(insert, spoken_text)`, `fallback_reason="bad_reply"` |
| **`which` Field** | `app/schemas/actions.py:Action` | For `insert`/`rewrite`: forced to `"last"`. For `replace`: must be `"first"`, `"last"`, `"all"` (missing defaults to `"last"`). Other strings rejected | Fallback -> `Action(insert, spoken_text)`, `fallback_reason="bad_reply"` |
| **Text Requirement** | `app/schemas/actions.py:Action` | `insert` and `rewrite` require non-empty `text.strip()` | Fallback -> `Action(insert, spoken_text)`, `fallback_reason="bad_reply"` |
| **Find Requirement** | `app/schemas/actions.py:Action` | `replace` requires non-empty `find.strip()` (text can be empty) | Fallback -> `Action(insert, spoken_text)`, `fallback_reason="bad_reply"` |
| **Extra Keys** | `app/schemas/actions.py:Action` | Extra keys ignored (`extra="ignore"`), but `"action"` is required (`"type"`-only rejected) | Rejects `"type"`-only replies |
| **Empty Box Target** | `app/services/action_service.py:process` | If `not box_text.strip()` and action is `replace` or `rewrite` | Fallback -> `Action(insert, spoken_text)`, `fallback_reason="not_allowed_empty_box"` |
| **Replace Match** | `app/services/action_service.py:process` | `find` must exist in `box_text` (case-sensitive or case-insensitive) | If not found anywhere in box: `action=None`, `used_fallback=True`, `fallback_reason="find_not_found"` |

---

## 5. Spark Step in Detail

### Message Construction
1. Tag stripping: Literal occurrences of `<box>`, `</box>`, `<spoken>`, `</spoken>` (case-insensitive) are stripped from both texts via `clean_text()`.
2. XML formatting: User message is formatted as:
   ```xml
   <box>{cleaned_box}</box>
   <spoken>{cleaned_spoken}</spoken>
   ```
3. System prompt variable: `SPARK_SYSTEM_PROMPT` loaded from [`app/prompts/spark_system.md`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/prompts/spark_system.md).

### API Call Dispatch (`app/services/llm_service.py:complete`)
Parameters passed to `client.chat.completions.create(...)`:
- **`model`**: Passed. Value: `settings.DEFAULT_LLM_MODEL` (`"muse-spark-1.3"`).
- **`messages`**: Passed. Value:
  ```python
  [
      {"role": "system", "content": SPARK_SYSTEM_PROMPT},
      {"role": "user", "content": user_message},
  ]
  ```
- **`response_format`**: Passed. Value: `ACTION_RESPONSE_FORMAT`:
  ```python
  {
      "type": "json_schema",
      "json_schema": {
          "name": "Action",
          "strict": True,
          "schema": {
              "type": "object",
              "properties": {
                  "action": {"type": "string", "enum": ["insert", "replace", "rewrite"], "title": "Action"},
                  "text": {"type": "string", "title": "Text"},
                  "find": {"type": "string", "title": "Find", "default": ""},
                  "which": {"type": "string", "enum": ["first", "last", "all"], "title": "Which", "default": "last"},
              },
              "required": ["action", "text", "find", "which"],
              "additionalProperties": False,
              "title": "Action",
          },
      },
  }
  ```
- **`reasoning_effort`**: Passed. Value: `"minimal"` (from `settings.SPARK_REASONING_EFFORT`, or optional override).
- **`max_tokens`**: **NOT passed** (absent from call kwargs).
- **`timeout`**: Configured at client instantiation (`timeout=20.0` on `AsyncOpenAI`), not per-call.

---

## 6. Error Map

| Exception Class | Raised Where | Caught Where | Final HTTP Status | Final Response Payload |
| :--- | :--- | :--- | :--- | :--- |
| **`HTTPException`** | `app/api/v1/process.py:33, 38` | FastAPI default exception handler | 413 or 400 | `{"detail": "<error message>"}` |
| **`InvalidRequestError`** | `app/core/validators.py:27, 48` | `app/api/errors.py:app_error_handler` | 400 | `{"detail": "<error message>"}` |
| **`InvalidAudioError`** | `app/core/audio.py:76, 80, 92, 98, 105, 113, 119, 128, 135, 149, 157`; `app/services/stt_service.py:88` | `app/api/errors.py:app_error_handler` | 400 (or 413 if payload limit) | `{"detail": "<error message>"}` |
| **`RateLimitedError`** | `app/services/stt_service.py:90`; `app/services/llm_service.py:80` | `app/services/action_service.py:94` (catches Spark rate limits and triggers fallback); if uncaught (e.g. from STT), caught by `app/api/errors.py:app_error_handler` | 429 | `{"detail": "Meta API rate limit exceeded"}` |
| **`MetaApiError`** | `app/services/stt_service.py:68, 76, 92, 94`; `app/services/llm_service.py:82, 84, 87` | `app/services/action_service.py:94` (catches Spark failures and triggers fallback); if uncaught (e.g. from STT), caught by `app/api/errors.py:meta_api_error_handler` | 502 | `{"detail": "Meta speech-to-text service error"}` |
| **`Exception` (unhandled)**| Any unexpected runtime crash | `app/api/errors.py:unhandled_exception_handler` | 500 | `{"detail": "Internal server error"}` |

---

## 7. Settings Audit (`app/core/config.py`)

| Setting Name | Default Value | Used In | Status |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | `"Vboard Backend"` | Never referenced in code | **Dead / Unused** |
| `ENVIRONMENT` | `"development"` | Never referenced in code | **Dead / Unused** |
| `DEBUG` | `True` | `app/api/v1/process.py:79` (toggles `response.timings_ms`) | Active |
| `PORT` | `8000` | Never referenced in code | **Dead / Unused** |
| `HOST` | `"0.0.0.0"` | Never referenced in code | **Dead / Unused** |
| `META_API_KEY` | `None` | `app/services/meta_client.py:17`, `app/services/llm_client.py:16` | Active |
| `META_BASE_URL` | `"https://api.meta.ai/v1"`| `app/services/meta_client.py:20`, `app/services/llm_client.py:17` | Active |
| `HF_TOKEN` | `None` | `eval/download_samples.py:32` | Active (eval only) |
| `DEFAULT_VOICE_MODEL` | `"muse-voice-transcribe-1.0"` | `app/services/stt_service.py:48` | Active |
| `MAX_AUDIO_BYTES` | `5 * 1024 * 1024` (5 MB) | `app/api/v1/process.py:28, 31, 32`, `app/core/audio.py:78, 79` | Active |
| `MIN_AUDIO_DURATION_S`| `0.3` | `app/core/audio.py:127, 130` | Active |
| `MAX_AUDIO_DURATION_S`| `60.0` | `app/core/audio.py:134, 137` | Active |
| `SILENCE_RMS_THRESHOLD`| `50.0` | `app/core/audio.py:156` | Active |
| `MAX_CONTEXT_TEXT_LENGTH`| `10000` | `app/core/validators.py:47, 50` | Active |
| `MAX_LANGUAGES_COUNT` | `5` | `app/core/validators.py:85` | Active |
| `DEFAULT_LLM_MODEL` | `"muse-spark-1.3"` | `app/services/llm_service.py:59` | Active |
| `SPARK_REASONING_EFFORT`| `"minimal"` | `app/services/action_service.py:84` | Active |
| `SARVAM_API_KEY` | `None` | Never referenced in code | **Dead / Unused** |
| `GEMINI_API_KEY` | `None` | Never referenced in code | **Dead / Unused** |
| `GROQ_API_KEY` | `None` | Never referenced in code | **Dead / Unused** |

---

## 8. Shared Clients

### 1. Meta HTTPX Client (`app/services/meta_client.py`)
- **Creation**: `init_meta_client()` creates a module-level `httpx.AsyncClient` with `base_url=settings.META_BASE_URL`, optional `Authorization: Bearer <META_API_KEY>`, and `timeout=Timeout(30.0, connect=5.0)`.
- **Sharing**: Retrieved via `get_meta_client()`. Raises `RuntimeError` if uninitialized or closed.
- **Teardown**: Closed via `close_meta_client()` (`await _client.aclose()`). Invoked on FastAPI application shutdown in `app/main.py:lifespan`.

### 2. Meta LLM OpenAI Client (`app/services/llm_client.py`)
- **Creation**: `init_llm_client()` creates a module-level `openai.AsyncOpenAI` instance with `api_key=settings.META_API_KEY or "none"`, `base_url=settings.META_BASE_URL`, `timeout=20.0`, and `max_retries=1`.
- **Sharing**: Retrieved via `get_llm_client()`. Raises `RuntimeError` if uninitialized or closed.
- **Teardown**: Closed via `close_llm_client()` (`await _client.close()`). Invoked on FastAPI application shutdown in `app/main.py:lifespan`.

---

## 9. Privacy Check (Logging Audit)

| File & Line | Log Statement Code | Printed Values | PII / Secret Risk |
| :--- | :--- | :--- | :--- |
| [`app/api/errors.py:33`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/api/errors.py#L33) | `logger.error("Unhandled error: {}", type(exc).__name__)` | Exception class name only | **Safe** (Zero text/stack leak) |
| [`app/core/validators.py:33`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/validators.py#L33) | `logger.info("Processing audio request for device: {}", device_id)` | Validated `device_id` string | **Safe** (Device identifier only; no speech/text) |
| [`app/services/llm_service.py:131`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/llm_service.py#L131) | `logger.info("LLM complete: elapsed_ms={:.2f}, prompt_tokens={}, completion_tokens={}, cached_tokens={}, reasoning_tokens={}", ...)` | Milliseconds, prompt tokens, completion tokens, cached tokens, reasoning tokens | **Safe** (Pure metrics numbers) |
| [`app/services/action_service.py:57`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/action_service.py#L57) | `logger.info("Action result: elapsed_ms=0.00, prompt_tokens=0, completion_tokens=0, cached_tokens=0, reasoning_tokens=0, action_type=None, used_fallback=False, fallback_reason=empty_speech")` | Static metric string and reason code | **Safe** |
| [`app/services/action_service.py:99`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/action_service.py#L99) | `logger.info("Action result: elapsed_ms=0.00, prompt_tokens=0, completion_tokens=0, cached_tokens=0, reasoning_tokens=0, action_type={}, used_fallback={}, fallback_reason={}", action.action, used_fallback, fallback_reason)` | Action name (`"insert"`), boolean, reason code (`"spark_error"`) | **Safe** |
| [`app/services/action_service.py:160`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/services/action_service.py#L160) | `logger.info("Action result: elapsed_ms={:.2f}, prompt_tokens={}, completion_tokens={}, cached_tokens={}, reasoning_tokens={}, action_type={}, used_fallback={}, fallback_reason={}", ...)` | Milliseconds, token numbers, action type string (`"insert"`/`"replace"`/`"rewrite"`/`None`), boolean, fallback reason | **Safe** |
| [`app/api/v1/process.py:57`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/api/v1/process.py#L57) | `logger.info("Timings for device {}: read_ms={:.2f}, guardrail_ms={:.2f}, stt_ms={:.2f}, spark_ms={:.2f}, total_ms={:.2f}, action_type={}, used_fallback={}, fallback_reason={}, prompt_tokens={}, completion_tokens={}, cached_tokens={}, reasoning_tokens={}", ...)` | `device_id`, numeric latency breakdown, action name, fallback boolean and reason code, token counts | **Safe** |

> [!NOTE]
> None of the logger statements print `spoken_text`, `box_text`, `transcript`, audio bytes, API keys, or prompt text. In `scripts/` (CLI evaluation tools), transcripts are printed to standard console output (`print()`) only when explicit CLI flags (`--show`, `--show-transcripts`) are enabled.

---

## 10. Tests and Evaluation

### Test Files (Total: 127 Pytest Tests)
- `tests/test_action_service.py`: Tests `action_service.process`, system prompt keywords, action fallbacks, replace reconciliation, and schema validation.
- `tests/test_audio.py`: Tests in-memory WAV validator against bad headers, channels, bit-depth, sample rates, min/max durations, and silence RMS.
- `tests/test_eval_endpoint_helpers.py`: Tests pricing and percentile calculation functions used in endpoint evaluations.
- `tests/test_eval_llm.py`: Tests CER calculation, punctuation normalization, scoring rules, and summary tables for LLM evaluations.
- `tests/test_eval_metrics.py`: Tests WER/CER computation and text formatting heuristics for ASR evaluation.
- `tests/test_llm_client.py`: Tests initialization, retrieval, singleton reuse, and closure of `AsyncOpenAI`.
- `tests/test_llm_service.py`: Tests chat completions, parameter forwarding (`reasoning_effort`, `response_format`), token metrics extraction, and error translation.
- `tests/test_meta_client.py`: Tests initialization, singleton lifecycle, authorization headers, and closing of `httpx.AsyncClient`.
- `tests/test_pipeline.py`: Tests pipeline execution order (guardrail -> STT -> Action), latency measurement, and fallback propagation.
- `tests/test_process_api.py`: Tests FastAPI endpoint `POST /v1/process`, input validators, upload limits, `DEBUG` flag timing exposure, privacy logging, and response structure.
- `tests/test_stt_service.py`: Tests Meta Muse STT multipart request format, language bias parameters, single retry on HTTP 500, and exception mapping.
- `tests/test_validators.py`: Tests device ID regex validation, context text character length limits, and language list canonicalization.

### Evaluation Scripts
- **`scripts/eval_audio.py`**:
  - Reads: `eval/metadata.csv` and audio files in `eval/audio/`.
  - Writes: Console summary report of Word Error Rate (WER) and Character Error Rate (CER) per language.
- **`scripts/eval_endpoint.py`**:
  - Reads: Audio files in `eval/audio/`.
  - Writes: Timestamped CSV output in `eval/results/endpoint_<timestamp>.csv` containing per-request server latency metrics, STT cost estimates, and error check results.
- **`scripts/eval_llm.py`**:
  - Reads: `eval/texttest.csv`.
  - Writes: Timestamped CSV output in `eval/results/llm_<timestamp>.csv` containing per-row pass/fail status, CER on target text, token consumption, and cost estimates.

---

## 11. Differences List

Architectural principles vs. current codebase:

1. **Unused Provider API Keys & Config Settings**:
   - File: [`app/core/config.py:17, 18, 20, 21, 84, 85, 86`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/config.py#L17-L86)
   - Description: `APP_NAME`, `ENVIRONMENT`, `PORT`, `HOST`, `SARVAM_API_KEY`, `GEMINI_API_KEY`, and `GROQ_API_KEY` are declared in `Settings` but never referenced anywhere in `app/`.
2. **Empty Stub Files**:
   - Files: [`app/api/v1/health.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/api/v1/health.py), [`app/core/logging.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/core/logging.py), [`app/db/models.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/db/models.py), [`app/db/session.py`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/db/session.py)
   - Description: These files contain zero statements (0 bytes) and are neither populated nor used by the runtime.
3. **Redundant Duplicate Model for Action Serialization**:
   - File: [`app/schemas/process.py:6`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/app/schemas/process.py#L6)
   - Description: `ActionModel` duplicates `Action` purely to make `find` and `which` optional in the final JSON response, requiring a manual mapping step in `app/api/v1/process.py:83-88`.
4. **HuggingFace Hub Dependency in Main Requirements**:
   - File: [`pyproject.toml:17`](file:///c:/Users/laksh/Desktop/Vboard/Vboard_backend/pyproject.toml#L17)
   - Description: `huggingface-hub` is listed under main runtime `dependencies` instead of optional `eval` dependencies, even though it is only used by `eval/download_samples.py`.

---

## 12. Flow Diagram for `POST /v1/process`

```mermaid
flowchart TD
    Client(["Client HTTP Request"]) --> UploadCheck["Read audio: UploadFile\n(limit: MAX_AUDIO_BYTES + 1)"]

    UploadCheck -->|len > MAX_AUDIO_BYTES| Err413["HTTP 413 Content Too Large"]
    UploadCheck -->|len == 0| Err400Empty["HTTP 400 Bad Request: Empty"]
    UploadCheck -->|Size OK| ValInputs["Validate Inputs\n(device_id, context_text, languages)"]

    ValInputs -->|Regex or Len Fail| Err400Val["HTTP 400 Bad Request: Invalid Parameter"]
    ValInputs -->|Valid| Guardrail["Audio Guardrail\n(WAV header, mono, 16/24kHz, 0.3-60s, RMS > 50)"]

    Guardrail -->|Invalid audio or silent| ErrAudio["HTTP 400 / 413: InvalidAudioError"]
    Guardrail -->|Audio Valid| STT["Meta Muse STT Service\n(POST /asr/transcribe)"]

    STT -->|500 Server Error| STTRetry{"Retry once\nafter 0.3s"}
    STTRetry -->|500 Fail| Err502["HTTP 502 Bad Gateway: MetaApiError"]
    STT -->|429 Rate Limit| Err429["HTTP 429 RateLimitedError"]
    STT -->|400 / 413| ErrAudio
    STT -->|200 OK| CheckEmptySpeech{"Is speech empty\nor whitespace?"}

    CheckEmptySpeech -->|Yes| ResEmpty["action=None\nfallback_reason='empty_speech'\nused_fallback=False"]
    CheckEmptySpeech -->|No| SparkCall["Spark LLM Service\n(muse-spark-1.3, minimal effort, strict schema)"]

    SparkCall -->|MetaApiError / RateLimitedError| FBSpark["action=Action(insert, spoken_text)\nfallback_reason='spark_error'\nused_fallback=True"]
    SparkCall -->|200 OK Response| ParseAction{"parse_action(reply)\nValid JSON schema?"}

    ParseAction -->|No / Invalid schema| FBBadReply["action=Action(insert, spoken_text)\nfallback_reason='bad_reply'\nused_fallback=True"]
    ParseAction -->|Valid Action| CheckEmptyBox{"Action is replace/rewrite\nAND box_text is empty?"}

    CheckEmptyBox -->|Yes| FBEmptyBox["action=Action(insert, spoken_text)\nfallback_reason='not_allowed_empty_box'\nused_fallback=True"]
    CheckEmptyBox -->|No| CheckReplace{"Is action == 'replace'?"}

    CheckReplace -->|No (insert/rewrite)| ActionOK["Action Accepted\nused_fallback=False"]
    CheckReplace -->|Yes| ReconcileFind{"find in box_text?\n(exact or case-insensitive)"}

    ReconcileFind -->|Exact match| ActionOK
    ReconcileFind -->|Case-insensitive match| ReconcileCase["Update find to exact box casing\nused_fallback=False"]
    ReconcileFind -->|Not in box| FBFindNotFound["action=None\nfallback_reason='find_not_found'\nused_fallback=True"]

    ResEmpty --> FinalizeResponse["Build ProcessResponse\ntimings_ms included if DEBUG=True\nLog numeric metrics & device_id"]
    FBSpark --> FinalizeResponse
    FBBadReply --> FinalizeResponse
    FBEmptyBox --> FinalizeResponse
    ActionOK --> FinalizeResponse
    ReconcileCase --> FinalizeResponse
    FBFindNotFound --> FinalizeResponse

    FinalizeResponse --> Output(["Return JSON Response (HTTP 200)"])
```

