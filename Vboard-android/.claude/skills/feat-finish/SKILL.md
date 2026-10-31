---
name: feat-finish
description: Finish a built Vboard feature: run unit tests, update code map, log progress, commit, and output the phone checklist. Use after feat-build completes.
---

Feature to finish: `$ARGUMENTS`

Follow these steps strictly in order:

1. **Unit Tests:**
   - If this feature added or modified pure Kotlin logic (e.g., `WavBuilder`, `ActionApplier`, language formatting, password check) and lacks a unit test, add a concise JVM unit test now.
   - Run `.\gradlew.bat testDebugUnitTest`. Fix any failures until all tests pass with **zero errors** (warnings are ok).

2. **Verify Code Map:**
   - Check `## Code map` in `CLAUDE.md` and update it if any block names or paths changed during `$ARGUMENTS`.

3. **Log Progress:**
   - Append an entry for `$ARGUMENTS` to `docs/progress.md` (create the `docs/` folder and file if missing; max 10 lines):
     - Feature name & summary of what changed
     - Files touched
     - Any `UNVERIFIED` items

4. **Commit (Safe Staging Only):**
   - Stage ONLY the tracked source/config files for this feature (never stage secrets, `local.properties`, `build/`, `.gradle/`, or `docs/`).
   - Commit with a clear message (e.g., `feat(F1a): implement keyboard shell and key layouts`). **Never push.**

5. **Phone Checklist & Hard Stop:**
   - Print the **Phone Checklist**: numbered steps in plain English for a tester with no Kotlin knowledge, each ending with `Expected: <result>`.
   - **STOP** immediately and wait for the user's phone test results.