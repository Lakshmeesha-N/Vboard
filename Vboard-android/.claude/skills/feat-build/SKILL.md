---
name: feat-build
description: Build ONE Vboard feature from the agreed plan. Use after the user approves a plan.
---

Feature to build: `$ARGUMENTS`

Follow these steps strictly:

1. **Strict Scope:**
   - Implement ONLY `$ARGUMENTS` according to the approved plan and `CLAUDE.md`. Do not build anything from later features.
   - Open and edit ONLY the blocks listed in the plan and `## Code map`. Do not re-read files you just wrote.

2. **Build & Verify:**
   - Run `.\gradlew.bat assembleDebug` (and `.\gradlew.bat testDebugUnitTest` if pure Kotlin logic or tests were added/changed).
   - Fix any compilation or test errors until they pass with **zero errors** (warnings are ok; do not loop on warnings). Paste only error lines if reporting an issue.

3. **Update Code Map (if needed):**
   - If you created a new block or renamed one, update `## Code map` in `CLAUDE.md` so it stays accurate.

4. **Hard Stop (Leave Finishing to `feat-finish`):**
   - Do NOT update `docs/progress.md` yet.
   - Do NOT run `git commit` yet.
   - End your response with the exact line: `Built. Run /feat-finish.`