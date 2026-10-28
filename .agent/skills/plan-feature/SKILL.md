---
name: plan-feature
description: Deep architectural blueprint mapping end-to-end data flow, files, functions, helpers, and execution steps before writing code in Vboard_backend or Vboard-android.
---


# Feature Architecture Planner (Read-Only Mode)

**CRITICAL:** Never create, edit, or delete project files.

1. Inspect relevant existing files before planning. Trace actual execution paths across both repositories when available.
2. Make a detailed, readable ASCII flow diagram the primary output, from feature trigger and input to final output.
3. Show actual file paths, classes, functions, helper calls, and their execution order.
4. Label important data types, parameters, return values, transformations, and API boundaries.
5. Use boxes, arrows, decision branches, and side notes to explain validation, authentication, processing, errors, retries, and fallbacks where relevant.
6. Include relevant Android components, backend services, databases, and external APIs.
7. Verify function relationships against the code. Never invent files, functions, or behavior.
8. Mark missing implementations as `PROPOSED` and unverifiable details as `UNKNOWN`. Separate existing behavior from planned changes.
9. Adapt the diagram to the feature; include only relevant details and keep supporting explanations brief.
10. Return the diagram first, followed by concise notes about important assumptions or gaps.

**Goal:** Explain the verified end-to-end feature flow clearly before implementation, without modifying any files.