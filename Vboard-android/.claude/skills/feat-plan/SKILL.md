---
name: feat-plan
description: Plan one Vboard feature (e.g., F1a, F3, F5) before writing code. Use when the user asks to plan or scope a feature.
---

Feature to plan: `$ARGUMENTS`

Follow these steps strictly:

1. **Check State (Minimal Reads):**
   - Read `docs/progress.md` (if it exists) to see completed features and existing files.
   - Read ONLY the existing source files listed in the `CLAUDE.md` **Code map** that this feature directly modifies. Do not search the whole repo.
   - Open `design/image.png` or `design/image1.png` ONLY if `$ARGUMENTS` involves UI (F1a, F1b, F2, F3, F4, F8, F9).
   - Read `contract/openapi.json` ONLY if `$ARGUMENTS` is `F5` or `F8` (if missing, stop and ask for it).

2. **Output Plan (Max 12 lines total):**
   - **Code Map Blocks:** Exact blocks to create or modify (using the names from `## Code map` in `CLAUDE.md`, plus XML/manifest files if needed).
   - **Pure vs. Android Split:** What logic goes into pure Kotlin unit-tested classes vs. Android Views/Services.
   - **Key Decisions & Edge Cases:** Specific rules for this feature (e.g., privacy, insets, code-point deletion, or contract limits) without repeating general `CLAUDE.md` rules.
   - **UNVERIFIED / Blockers:** Anything unverified or missing required before coding.

3. **Hard Stop:**
   - Do NOT write code, create files, edit files, or run Gradle commands.
   - End your response with the exact line: `Say ok to build.`