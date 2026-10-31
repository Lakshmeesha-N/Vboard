---
name: plan-feature
description: Trace existing code and produce a verified end-to-end architecture plan before implementing features in Vboard_backend or Vboard-android.
---

# Feature Architecture Planner

## Rules

* **Read-only:** Never create, edit, delete, or modify project files.
* Inspect relevant existing code before planning. Trace both backend and Android code when available and relevant.
* Follow actual callers, callees, data transformations, and control flow. Never invent files, functions, APIs, or behavior.
* Label unimplemented changes as `PROPOSED` and unverifiable details as `UNKNOWN`. State repository or inspection limitations explicitly.
* Respect `AGENT.md` security, privacy, and project-boundary rules.

## Planning Process

1. Identify the feature entry point, inputs, and expected outputs.
2. Trace the execution sequence through relevant files, classes, functions, and helpers.
3. Map validation, authentication, authorization, processing, external services, database operations, errors, retries, fallbacks, and side effects where applicable.
4. Record important data types, transformations, API contracts, and return values when verified.
5. Separate existing behavior from proposed changes and list assumptions or unresolved questions.

## Required Output

1. **End-to-end ASCII flow diagram** using clear boxes, arrows, branches, and labels.
2. **File and function map** listing verified files and their roles.
3. **Proposed changes** identifying new or modified components.
4. **Assumptions and unknowns** requiring confirmation.

Keep the plan accurate, readable, and concise. Avoid unrelated recommendations and repeated explanations.

## Stop Condition

Present the plan only, then stop. Do not implement anything until the user explicitly approves with `go`.