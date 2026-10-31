# VBoard — Agent Instructions

## 1. Project Overview

VBoard is a privacy-first AI voice keyboard monorepo.

- `Vboard_backend/` — Python FastAPI backend for speech-to-text (STT), text cleanup, formatting, translation, authentication, and health checks.
- `Vboard-android/` — Kotlin Android keyboard application.
- `.agent/skills/` — Task-specific Antigravity skills.

Understand the existing architecture before making changes. Do not assume an implementation exists without inspecting the source code.

## 2. Priority Order

Follow these priorities in order:

1. **Security and Privacy:** Never retain or expose user audio, transcripts, or sensitive text unnecessarily. Validate inputs and protect credentials.
2. **Low Latency:** Prefer asynchronous I/O, efficient processing, low memory usage, and minimal unnecessary operations.
3. **Maintainability:** Write readable, modular, typed code that follows existing project conventions.

## 3. Project Boundaries

### Backend
- Keep backend changes inside `Vboard_backend/`.
- Follow the existing FastAPI architecture and project configuration.
- Reuse existing services, utilities, and dependencies where appropriate.

### Android
- Keep all new Android voice-related code inside `Vboard-android/.../voice/`.
- Never modify upstream or forked Android files unless the user explicitly identifies the exact file and authorizes the change.
- Follow the existing Android architecture and coding conventions.
- Do not introduce Jetpack Compose unless explicitly requested.

## 4. Security and Privacy Rules

- Never read, print, expose, or commit `.env` files, API keys, tokens, or credentials.
- Never log or persist user audio, transcripts, prompts, or sensitive text.
- Do not weaken authentication, authorization, validation, or other security controls.
- Validate external inputs and handle errors safely.
- Do not use production credentials or perform destructive operations without explicit authorization.

## 5. Development Rules

- Inspect relevant source files, configuration, dependencies, and existing tests before making changes.
- Use `pyproject.toml` and the existing project configuration as the source of truth for backend dependencies and tooling.
- Do not invent APIs, functions, schemas, or expected behavior.
- Do not add dependencies or introduce new architectural patterns without permission.
- Avoid unrelated refactoring and unrequested features.
- Prefer minimal changes that preserve existing functionality.
- Never overwrite or delete existing work unnecessarily.
- Explain assumptions and identify missing specifications instead of guessing.

## 6. Agent Workflow

- Do not automatically chain skills or run autonomous implementation loops.
- Do not start implementing a feature without an approved plan.
- Before making changes, explain the intended changes and identify the exact files involved.
- Implement in small steps, generally touching no more than 3–4 files per step.
- After each step, provide a summary of no more than three lines and stop.
- Continue only when the user gives the next instruction.

## 7. Skill Activation Rules

Use skills only under these conditions:

| Skill | Activation |
|---|---|
| `plan-feature` | When the user explicitly requests a feature plan. |
| `build-feature` | Only after a plan exists and the user explicitly approves with `go`. |
| `write-tests` | Only when the user explicitly requests test writing or execution. |
| `security-review` | Only when the user explicitly requests a security or privacy review. |

Do not automatically activate one skill after another.

## 8. Testing and Verification

- Do not run tests automatically after implementation.
- Use existing project testing conventions and dependencies.
- Mock external services when appropriate.
- Never claim that code or tests work unless the relevant checks were actually performed.
- Report failures and unverified behavior honestly.