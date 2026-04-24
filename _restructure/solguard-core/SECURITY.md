# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security bugs.

Email: security@solguard.dev (or the maintainer's email on their GitHub profile until that alias is live).

Include:
- A description of the issue and its impact.
- Steps to reproduce or a proof-of-concept.
- Your preferred disclosure timeline (we target 72-hour initial response).

## Scope

In scope:
- `agent/` FastAPI service (auth, rate-limiting, webhook verification, LLM output handling).
- `programs/solguard-registry/` on-chain Anchor program.
- Notifier fanout HMAC signing (`agent/notifiers.py`).

Out of scope:
- Issues in third-party dependencies that are already tracked upstream.
- DoS via overwhelming the SSE endpoint (known-limitation; tracked in issues).

## Threat model snapshot

- **Untrusted input sources:** Helius webhooks (HMAC-verified), public REST endpoints (rate-limited), LLM outputs (validator-sanitized in `claude_engine._validate_result`).
- **Trusted:** Local config via env vars, the SQLite DB file, the on-chain program upgrade authority.
- **Secrets at rest:** `.env` file is gitignored. Never bake secrets into Docker images — use `--env-file` or secret managers.

## Past audits

See [`docs/AUDIT_REPORT.md`](./docs/AUDIT_REPORT.md) in the main SolGuard repo for the v2 audit pass (3 Critical / 4 High / 6 Medium findings, all resolved).
