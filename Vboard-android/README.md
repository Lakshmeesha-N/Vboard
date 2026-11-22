# Vboard-android

AI-first Android keyboard (`InputMethodService`) for Kannada, Hindi, English,
and code-mixed speech (Kanglish, Hinglish). Records voice in memory, sends it
with textbox context to the Vboard backend, and applies the returned edit
action. See `CLAUDE.md` for the full build contract.

## Dependencies

Production (in `gradle/libs.versions.toml` + `app/build.gradle.kts`):

- **OkHttp** (`com.squareup.okhttp3:okhttp`) — Apache 2.0 — multipart
  `POST /v1/process` to the backend (connect 5 s, whole call 20 s).
- **kotlinx.coroutines-android** (`org.jetbrains.kotlinx:kotlinx-coroutines-android`)
  — Apache 2.0 — network on `Dispatchers.IO`, textbox/UI on the main thread.
- **AndroidX + Material** (`core-ktx`, `appcompat`, `constraintlayout`,
  `activity-ktx`, `material`) — Apache 2.0 — settings/onboarding UI.
- **org.json** (built into Android, no extra artifact) — JSON parsing of
  `/v1/process` responses in `ProcessResponse.kt`.

Test-only:

- **`org.json:json`** (`testImplementation`) — JSON license (MIT-like) —
  real `org.json` for plain-JVM unit tests, because the `android.jar`
  stubs throw on any `android.*`/`org.json` call. Listed separately so it
  never ships in the APK.
- **JUnit 4** (`testImplementation`) — EPL-1.0 — unit tests.

## Template boilerplate

`app/src/test/java/app/vboard/ExampleUnitTest.kt` is the Android Studio
template sample (kept). Everything under `app.vboard` is hand-written for
Vboard; no code is copied from other keyboard projects.

## Word list

English word suggestions ship an on-device asset,
`app/src/main/assets/words_en.txt` (20,000 words, `word<TAB>rank` per line),
built by `tools/suggest/build_words.py` from `tools/suggest/core_words.txt`
(hand-ordered core-100, rank = line order) topped up from the 12dicts lists.
The asset is on-device only: it ships in the APK, is read locally at runtime,
and is never uploaded anywhere.

Word-list sources:

- **12dicts** (Alan Beale) — public domain; the compiler requests
  acknowledgment of use. Used bands: `3esl.txt`, `2of4brif.txt`
  (`2of12inf` is never used).
- **SCOWL / ESDB** (Kevin Atkinson, Copyright 2000-2018) — MIT-like:
  permission to use, copy, modify, distribute, and sell the word lists and
  derived output is granted without fee, provided the copyright notice
  appears in all copies and both notices appear in supporting documentation.
