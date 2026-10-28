---
name: build-feature
description: Implement an explicitly approved feature plan in Vboard_backend or Vboard-android using small, secure, verified changes.
---

# Build Feature

## Activation
- Run only after `plan-feature` has produced a plan and the user explicitly approves it by saying `go`.
- If no approved plan exists, stop and request the planning step.
- Follow `AGENT.md` and the approved plan.

## Before Coding
- Inspect the relevant source files, configuration, dependencies, and existing patterns.
- Confirm the files and functions that need changes.
- Identify assumptions, missing specifications, or conflicts before implementation. Never invent APIs or behavior.

## Implementation
- Implement only the approved scope. Do not add unrequested features or perform unrelated refactoring.
- Make small, controlled changes, generally affecting no more than 4–5 files per step.
- Preserve existing functionality and follow project architecture and conventions.
- Prioritize security and privacy, then latency and maintainability.
- Never log or expose secrets, audio, transcripts, or sensitive data.
- Do not weaken security controls, modify upstream forked Android files, or add dependencies without authorization.
- Do not run tests automatically; use `write-tests` only when the user explicitly requests testing.

## Step-by-Step Workflow
1. Explain the next implementation step and list the exact files and functions to change.
2. Implement only that step.
3. Summarize the changes in no more than three lines and identify any issues.
4. Stop and wait for the user's next instruction before continuing.

## Verification
- Check the changes for correctness using available, relevant checks that do not conflict with the testing rules.
- Never claim tests or checks passed unless they were actually executed successfully.
- Report errors, unresolved assumptions, and anything that could not be verified.

## Final Report
Summarize the files changed, implementation completed, verification actually performed, and remaining work. Do not claim the entire feature is complete if any approved part remains unfinished.