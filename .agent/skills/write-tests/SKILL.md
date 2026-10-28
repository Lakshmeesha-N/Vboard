---
name: write-tests
description: Write reliable async pytest tests for Vboard_backend using verified application behavior, appropriate mocks, and accurate test results.
---

# Write Tests

## Rules
- Inspect the actual application code, dependencies, configuration, and existing tests before writing tests. Never invent routes, functions, or expected behavior.
- Never delete or overwrite existing work unnecessarily. Follow existing project conventions.
- Mock external APIs, STT, LLM, translation, and other external services. Use an isolated test database when database behavior itself is under test.
- Never use production credentials, weaken security, or change production code without authorization.
- Use existing dependencies. Do not install packages without permission.

## Test Design
- Cover relevant success, validation, boundary, failure, security, and regression scenarios based on actual requirements.
- Each test should verify a specific behavior with meaningful assertions.
- Use `pytest`, `pytest-asyncio`, `httpx`, `AsyncMock`, `MagicMock`, and FastAPI dependency overrides where appropriate.
- Use `pytest-mock` only if it is already installed.
- Test async FastAPI endpoints with `httpx.ASGITransport` and `httpx.AsyncClient`, adapted to the actual application setup.
- Mock startup dependencies if they would contact external services.
- Restore dependency overrides and modified state after each test, preferably using fixtures with cleanup. Never modify `router.dependencies` to bypass security.

## Execution and Debugging
- Reuse suitable fixtures and place shared fixtures in `tests/conftest.py` when useful.
- Run targeted tests first, then the broader test suite when appropriate.
- Diagnose failures using actual error messages and code evidence. Make only authorized, minimal fixes.
- Never change test expectations merely to make tests pass.
- Never claim tests passed unless they were executed successfully.

Example commands (adapt paths to the project):

```bash
pytest tests/test_health.py -v
pytest -v
```

## Explain Results
For beginners, briefly explain what each test checks and why it matters. For failures, report the expected result, actual result, relevant error, and likely cause based on evidence.

## Final Report
- List created or modified test files with exact paths.
- Summarize the scenarios covered.
- Report the commands executed and actual pass/fail/error/skip results.
- Identify unresolved failures and necessary next steps.
- State that passing tests verify only the behaviors tested.