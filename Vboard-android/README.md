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
