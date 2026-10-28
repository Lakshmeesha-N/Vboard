---
name: security-review
description: Review Vboard_backend for verified security and privacy risks, prioritize findings, and recommend minimal fixes.
---

# Security Review

## Rules
- Inspect relevant source code, configuration, dependencies, and existing security controls before drawing conclusions.
- Verify findings against the actual implementation. Never invent vulnerabilities or claim unverified behavior.
- Follow `AGENT.md` and respect project boundaries.
- Never expose secrets, credentials, audio, transcripts, or other sensitive data.
- Do not weaken security controls, install dependencies, or modify production code without authorization.
- Do not perform destructive tests or test production systems without explicit authorization.

## Review Scope
Check relevant areas, including:
- Authentication, authorization, and JWT validation.
- Secret management and insecure configuration.
- Input validation, injection risks, and unsafe file handling.
- Rate limiting and abuse prevention.
- Sensitive-data exposure, logging, and privacy.
- Database access, dependency vulnerabilities, and error handling.

Inspect only areas relevant to the requested review.

## Findings
For each finding, report:
1. **Severity:** Critical, High, Medium, Low, or Informational.
2. **Location:** Exact file and relevant function or code section.
3. **Evidence:** What the code actually does.
4. **Impact:** How the issue could affect security or privacy.
5. **Recommended fix:** The smallest effective change.

Clearly distinguish confirmed vulnerabilities from potential risks and informational observations.

## Verification
- Run relevant security checks only when authorized and available.
- Report actual results and identify anything that could not be verified.
- Recommend regression tests for confirmed vulnerabilities. Use `write-tests` when test implementation or execution is requested.
- Never claim an issue is fixed without verification or declare the application fully secure merely because no findings were detected.

## Final Report
Summarize prioritized findings, supporting evidence, recommended fixes, verification results, and remaining risks. Keep explanations clear and concise.