# CLAUDE.md — Vboard-android

Read this file fully before any task. Keep responses, logs, and notes short.

## 1. Scope & Role
We are building **Vboard**, an AI-first Android keyboard (`InputMethodService`) for Kannada, Hindi, English, and code-mixed speech (Kanglish, Hinglish).
- **Your ONLY job:** Build and maintain the Android keyboard inside `Vboard-android`.
- **Out of scope:** The Python backend (`../Vboard_backend`) is already built. NEVER read, edit, or run anything outside `Vboard-android`. Write backend change requests in `docs/backend-requests.md` and tell the user.

### Core User Flow
1. User taps the voice button in the top bar and speaks.
2. Top bar shows the recording wave pill; keyboard records audio in memory and reads current textbox context.
3. User taps `✓` to send audio + context to the backend (`Meta Muse` STT + `Meta Spark` LLM), or taps `✕` to cancel.
4. Backend returns **ONE** action (`insert`, `replace`, or `rewrite`).
5. Keyboard applies the action to the textbox. Default behavior is cleanup (spelling, punctuation, structure) while keeping the spoken language. Translation happens only when requested.

---

## 2. Visual Design & Top Bar States (`design/image.png` & `design/image1.png`)
Inspect `design/image.png` and `design/image1.png` before building UI. Match the dark theme, keycaps, and top-bar states:

### Keyboard Surface & Keycaps
- **Colors:** Dark background (`#121316` / `#17181B`), charcoal rounded keycaps (`#282A2F`) with white labels (`#FFFFFF`), darker modifier keys (`?123`, Shift, Backspace, Enter) with subtle blue/teal tint on the Enter icon[cite: 1, 2].
- **Rows:** `1`–`0` number row (or top-right superscripts on `Q`–`P`), QWERTY rows, bottom row with pill `?123`, `,`, wide Spacebar showing the active language label, `.`, and pill Enter key[cite: 1, 2].

### Top Bar — State 1: Idle Mode (`design/image1.png`)
- **Only the voice and AI buttons are real. Leave the other slots out, because the demo may show only what we built.**
- Right-aligned circular dark icon buttons (`#25272C`):
  - **Voice Input Button:** Circular dark button with vertical 5-bar waveform icon (`|||`)[cite: 2].
  - **AI Action Button:** Circular dark button with a glowing blue/purple ring (`O`)[cite: 2].

### Top Bar — State 2: Active Recording Mode (`design/image.png`)
- Clicking the voice button turns the top bar into a **full-width dark pill** (`#1E2025`, stadium corners)[cite: 1]:
  - **Animated Dotted Waveform:** Horizontal micro-bars/dots (`••••••••••••`) animated by live mic amplitude from `AudioRecord`[cite: 1].
  - **Cancel (`✕`):** Grey `✕` icon; aborts recording, clears RAM buffer, and returns to Idle Mode[cite: 1].
  - **Confirm (`✓`):** Solid white circle (`#FFFFFF`) with dark checkmark (`✓`) on the far right; stops recording and sends the in-memory WAV to the backend[cite: 1].

---

## 3. Hard Rules & Code Ownership
- **Original Code Only:** Write all code from scratch under package `app.vboard`. NEVER copy code from FlorisBoard, HeliBoard, AOSP LatinIME, or any other keyboard.
- **Dependencies:** Keep libraries minimal. List every library in `README.md` under `## Dependencies` (Name, License, Why). Note in `README.md` which files are Android Studio template boilerplate.
- **Git & Secrets:** Never commit secrets, API keys, `local.properties`, `build/`, `.gradle/`, or `docs/`. Do not push unless asked.
- **Token Efficiency:** Use grep/file search before opening files. Paste only build errors, not full logs. Do not re-read files just written.

---

## 4. Privacy & Security (Non-Negotiable)
- **Zero Disk Audio:** Never write audio to disk. Record in memory (`ByteArray`/`ByteBuffer`), send, and clear in `finally` blocks.
- **Zero Content Logging:** Never log, store, or print audio, spoken text, or textbox text (no `Log.d` of content, analytics, or crash reports).
- **Password Fields:** Check `EditorInfo.inputType` on `onStartInput`/`onStartInputView`. For any password/PIN variant, disable voice/AI buttons and show a short hint. Never read or send text from password fields.
- **Data Minimization:** Send only what the contract requires.

---

## 5. IME Engineering Rules
- **Key Input:** Trigger keys on `MotionEvent.ACTION_DOWN` with visual pressed state and `HapticFeedbackConstants.KEYBOARD_TAP`.
- **Insets:** Respect bottom `WindowInsets` so the bottom row never overlaps the system navigation bar.
- **Lifecycle:** Cancel coroutines, `AudioRecord`, and HTTP calls cleanly on `onFinishInputView()` and `onDestroy()`.
- **Threading:** Run `InputConnection` and View updates on the main thread; run audio and network I/O on `Dispatchers.IO`.

---

## 6. Tech Stack & Commands
- **Stack:** Kotlin, plain Android `View` system (NO Jetpack Compose). `minSdk = 24`, package `app.vboard`.
- **Libraries:** `OkHttp` (HTTP/multipart), `kotlinx.coroutines`, `kotlinx.serialization` or `Moshi` (JSON).
- **Hardware:** Windows laptop (8 GB RAM). **NEVER start an emulator.** User tests on a real phone over USB.
- **Commands:**
  - Build: `.\gradlew.bat assembleDebug`
  - Unit Tests: `.\gradlew.bat testDebugUnitTest`
  - Install: `.\gradlew.bat installDebug`
- **Done Criteria:** Build and unit tests must pass. Never claim a feature "works on the phone".

---

## 7. Backend Contract
Before writing network code (F5), read `contract/openapi.json`. If missing, **STOP** and ask the user for it. Use exact names from `contract/openapi.json`.

### `POST /v1/process` (`multipart/form-data`)
- `audio`: WAV in memory, mono, 16-bit PCM, 16000 Hz (24000 Hz also accepted). 0.3s–60s, max 5 MB (`413` if larger, `400` if empty).
- `device_id`: Random UUID generated once on first run and saved in `SharedPreferences`.
- `context_text`: Full current textbox text (max ~10,000 chars; may be empty).
- `languages`: 1 to 5 language names joined by a comma with **NO spaces** (e.g., `Kannada,Hindi,English`), in the order picked by the user (`UNVERIFIED` whether order matters to backend).
  - **Allowed names (25, exact spelling):** `Arabic`, `Bengali`, `Dutch`, `English`, `French`, `German`, `Hebrew`, `Hindi`, `Indonesian`, `Italian`, `Japanese`, `Kannada`, `Korean`, `Malay`, `Mandarin Chinese`, `Marathi`, `Polish`, `Portuguese`, `Spanish`, `Tagalog`, `Tamil`, `Telugu`, `Thai`, `Turkish`, `Vietnamese`.

### Response (verified)
- Fields: `transcript`, `timing_ms`, `audio_duration_ms`, `action` (object or `null`), `used_fallback`, `note`, `timings_ms` (debug only).
- `action` object: `action` (`insert` | `replace` | `rewrite`), `text`, `find` (can be `null`), `which` (can be `null`).

### Applying Actions
- `insert`: Insert `text` at cursor (ignore `find`, `which`).
- `rewrite`: Replace entire textbox with `text` (ignore `find`, `which`).
- `replace`: Find `find` (ignore case) and replace with `text`. `which` = `"first"`, `"last"`, or `"all"` (treat unknown/number values as `"last"`).
- `action == null`: Change nothing, show a short message.
- `used_fallback == true`: Backend returned a plain `insert` of raw transcript; apply normally and show a small hint.
- **Errors:** Handle offline, timeout, `400`, `413`, `429`, `502` with a short message in the top bar. Never crash or lose user text.

---

## 8. Android Implementation Notes
- **Permissions:** Manifest needs `INTERNET` and `RECORD_AUDIO`. Keyboard checks `RECORD_AUDIO` and opens the Settings `Activity` if missing.
- **Textbox Read/Write:** Read via `getTextBeforeCursor(n, 0)` + `getTextAfterCursor(n, 0)` (handle `null`, cap length). Edit inside `beginBatchEdit()` / `endBatchEdit()` using `deleteSurroundingTextInCodePoints()` (for Kannada combining characters) and `commitText()`.
- **Undo:** Keep previous full text in memory to restore on Undo tap.
- **Audio:** Build tap-to-record with `✕` and `✓` first, as in the mockup[cite: 1]. Hold-to-talk is optional, later. Ignore `< 0.3s`, cap at `30s`. `AudioRecord` at 16000 Hz, mono, 16-bit PCM + 44-byte WAV header in memory.
- **Dev Network:** Cleartext HTTP allowed in `debug` only (`network_security_config.xml`). USB route: `adb reverse tcp:8000 tcp:8000` (`http://127.0.0.1:8000`).

---

## 9. Feature Order (One Feature Per Run)
Do **ONE** item per run in this order:
- **F1a. Keyboard Keys & Insets:** `InputMethodService`, dark keycaps matching `design/image.png`[cite: 1], QWERTY rows, Shift/Caps Lock, Backspace, Spacebar with language label, `?123`, Enter (respecting `imeOptions`), Globe key (`switchToNextInputMethod`), bottom navigation inset padding, and basic Settings Activity with system IME settings button.
- **F1b. Top Bar Shell:** Idle top bar matching `design/image1.png` with ONLY the Voice button (`|||`) and glowing ring AI button (`O`)[cite: 2] (no placeholder Apps/GIF/Theme icons).
- **F2. Symbols & Repeat:** Number/symbol layer (`?123` / `ABC`), punctuation, and repeating Backspace on hold (by code points).
- **F3. Onboarding & Settings:** First-open screen (enable keyboard + request `RECORD_AUDIO`). Language picker: `Kannada`, `Hindi`, `English` at top + 22 others in a scrollable list; require 1–5 selections, preserve pick order, save as comma-separated with no spaces in `SharedPreferences`. Backend URL field in Settings.
- **F4. Recorder & Wave Pill:** Tap-to-record top bar pill matching `design/image.png` (live dotted waveform `••••••••••••`, `✕` cancel, white `✓` confirm, processing state)[cite: 1] + in-memory WAV `AudioRecord`. (Hold-to-talk is optional, later.)
- **F5. Backend Client + INSERT:** Read `contract/openapi.json`, build `OkHttp` multipart client, wire `insert` end-to-end.
- **F6. Action Engine & Undo:** Pure function `applyAction(box, action)` with JVM unit tests (insert, rewrite, replace first/last/all, ignore case, not found = no change, Kannada text, empty box). Wire rewrite, replace, and top-bar Undo button.
- **F7. Errors & Safety:** Password field lockout, missing permission prompt, network/HTTP error messages (`400`, `413`, `429`, `502`, offline, timeout).
- **F8. Style Chips & Cleanup:** Wire AI button and chips (Shorter, Professional, Translate). **BLOCKED** until backend `/v1/edit` exists—ask user first.
- **F9. Polish & Docs:** Visual check against `design/image.png` and `design/image1.png`, dark theme polish, and `README.md` (`Built by us` and `Dependencies`).

### After Every Feature
1. Run `.\gradlew.bat assembleDebug` and `.\gradlew.bat testDebugUnitTest` until both pass with **zero errors**.
2. Append to `docs/progress.md` (gitignored, max 15 lines per entry): what changed, files touched, anything `UNVERIFIED`, and the **Phone Checklist** (numbered plain-English steps with `Expected:` results).
3. Commit with a clear message (do not push).
4. Print the Phone Checklist, then **STOP and wait**.

---

## 10. Code Style
- Small classes, one job per file under `app.vboard`.
- Keep pure logic (WAV header, `applyAction`, language formatting) free of Android imports for JVM unit tests.
- No dead code, no `TODO` comments, comments only where reason is non-obvious.
## Code map
Each block is one small file or class. To change or fix something, open only that block.
Use this map first, don't search the whole project. After each feature, update the map.
Planned blocks (rename if you must, but keep the map true):
- KeyboardService: the InputMethodService, connects the other blocks
- KeyboardView / KeyLayouts / KeyButton: keys and layouts (key row height: KEY_ROW_HEIGHT_DP = 51)
- TopBarView: idle bar and recording pill
- VoiceBarsDrawable: white 5-bar voice icon drawable (used by TopBarView)
- WaveformView: the live dotted wave
- Recorder: AudioRecord to in-memory WAV
- WavBuilder: WAV header (pure Kotlin, unit tested)
- BackendClient: OkHttp call to /v1/process
- ActionApplier: applyAction logic (pure Kotlin, unit tested)
- TextBoxEditor: reads and writes the textbox through the input connection
- SettingsStore: language choice, backend URL, device ID, mic-requested flag
- LanguageList: 25 names, pinned picker order, 1-to-5 rule, CSV format/parse (pure Kotlin, unit tested)
- MainActivity: thin onboarding host (enable/choose/mic/languages/URL), delegates to SettingsStore/LanguageList

11. Invoke the `security-fixer` subagent to audit and automatically fix security issues before declaring the feature complete.

Java for Gradle: JAVA_HOME=C:\Program Files\Android\Android Studio\jbr. Android SDK: C:\Users\laksh\AppData\Local\Android\Sdk. Do not search for them.