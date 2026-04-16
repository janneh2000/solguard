# SolGuard Security Audit Report (v2.0)

**Scope:** on-chain Anchor program, off-chain Python agent, public dashboard.
**Methodology:** Solana Foundation audit style — findings classified by severity, with description, impact, recommendation, and remediation status. Every finding below is tied to a concrete file/line in the repository.
**Auditor:** Autonomous pass prior to Colosseum Phase 3 submission.

---

## Summary

| Severity | Open | Fixed in v2 |
| -------- | ---- | ----------- |
| Critical | 0    | 3           |
| High     | 0    | 4           |
| Medium   | 0    | 6           |
| Low / Info | 2  | 5           |

All Critical and High findings from the v1 pass are remediated in v2.

---

## Critical findings (fixed)

### C-01 — Anchor program missing input validation on `risk_level` / `event_type`
- **File:** `programs/solguard-registry/src/lib.rs`
- **v1:** The `record_alert` instruction accepted any `u8` for `risk_level` and `event_type`. The `InvalidRiskLevel` / `InvalidEventType` errors were declared but never returned.
- **Impact:** A compromised authority (or a bug in the agent) could persist garbage data on-chain and poison any consumer of `AlertRecorded` events.
- **Fix (v2):** Added `require!(risk_level <= MAX_RISK_LEVEL, …)` and `require!(event_type <= MAX_EVENT_TYPE, …)` at the top of `record_alert`. Bounded-enum constants exported.
- **Status:** ✅ Fixed.

### C-02 — Integer overflow on the alert counter
- **File:** `programs/solguard-registry/src/lib.rs`
- **v1:** `registry.total_alerts += 1;` used wrapping default. At `u64::MAX` the counter wraps silently and the next `alert` PDA seed collides with alert #0, causing a permanent DoS on the registry.
- **Fix (v2):** `checked_add(1).ok_or(SolGuardError::CounterOverflow)?`
- **Status:** ✅ Fixed.

### C-03 — Placeholder `declare_id!` mismatched real deployment
- **File:** `programs/solguard-registry/src/lib.rs`, `Anchor.toml`
- **v1:** `declare_id!("SGRDxxxx…")` was a placeholder; the real devnet deployment is `5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM`. Anchor's program-id check would reject every instruction.
- **Fix (v2):** `declare_id!` set to the real program id in both the program source and `Anchor.toml` (`devnet` + `mainnet` stanzas).
- **Status:** ✅ Fixed.

---

## High findings (fixed)

### H-01 — No authentication on the Helius webhook
- **File:** `agent/main.py`
- **v1:** `/webhooks/helius` accepted any JSON body and queued alerts, enabling alert-spoofing and persistent-storage pollution.
- **Fix (v2):** Added HMAC-SHA256 verification over the raw body using `HELIUS_WEBHOOK_SECRET`; `Bearer` token fallback. `hmac.compare_digest` used for constant-time comparison.
- **Status:** ✅ Fixed.

### H-02 — `/api/trigger-test` was publicly callable
- **File:** `agent/main.py`
- **v1:** Anonymous POST could inject fake `CRITICAL` alerts at will.
- **Fix (v2):** Gated behind `SOLGUARD_ADMIN_TOKEN` header; endpoint returns `503 admin_disabled` if no token is configured. Public demo use is now routed through `/api/replay/drift`, which produces *labelled* replay events only.
- **Status:** ✅ Fixed.

### H-03 — Permissive CORS (`*` + credentials)
- **File:** `agent/main.py`
- **v1:** `allow_origins=["*"]` with `allow_credentials=True`.
- **Fix (v2):** Allow-list via `SOLGUARD_CORS_ORIGINS`; credentials disabled by default; only `GET`, `POST`, `OPTIONS` permitted.
- **Status:** ✅ Fixed.

### H-04 — `solguard_alerts.db-shm` / `-wal` tracked by git
- **v1:** SQLite WAL/SHM files were committed to the repo, leaking historical alert data and creating merge conflicts.
- **Fix (v2):** Removed from the index with `git rm --cached`; `.gitignore` updated with `*.db-shm`, `*.db-wal`, `*.db-journal`.
- **Status:** ✅ Fixed.

---

## Medium findings (fixed)

### M-01 — No rate limiting
- **File:** `agent/main.py`
- **Fix:** In-process token-bucket limiter on every `/api/*` and `/webhooks/*` route (60 req/min / 120 req/min respectively, keyed by `X-Forwarded-For`-aware client IP).

### M-02 — SSE client queue unbounded
- **File:** `agent/main.py`
- **Fix:** `MAX_SSE_CLIENTS` guard returns `503` once the cap is reached. Dead queues are reaped on full or cancelled paths.

### M-03 — Nonce monitor fetched every transaction serially
- **File:** `agent/watchers/nonce_monitor.py`
- **v1:** Sequential `get_transaction` calls per signature → rate-limit risk on public RPCs.
- **Fix (v2):** Bounded-concurrency via `asyncio.Semaphore`, LRU-deduped alert firing, tighter try/except scoping per-signature.

### M-04 — No input validation on `/api/alerts?risk_level=`
- **File:** `agent/main.py`, `agent/database.py`
- **Fix:** `risk_level` must match `{LOW,MEDIUM,HIGH,CRITICAL}`; `limit` clamped to `[1, 500]`. Database layer enforces the same allow-list as defence-in-depth.

### M-05 — LLM output not validated
- **File:** `agent/claude_engine.py`
- **v1:** The agent parsed Claude's JSON and stored it raw. A prompt-injection payload could store rogue strings in the database.
- **Fix (v2):** `_validate_result()` coerces unknown risk levels to `MEDIUM`, bounds string lengths, caps indicator arrays, and drops unknown `attack_pattern_match` values.

### M-06 — No CSP / security headers on the dashboard
- **File:** `vercel.json`, `dashboard/index.html`
- **Fix:** Strict `Content-Security-Policy` meta + HSTS, COOP/CORP, Permissions-Policy, Referrer-Policy at the edge.

---

## Low / Informational

### L-01 — Structured logging
- **v1:** `print()` calls throughout. Acceptable for a hackathon; recommend `logging` module with JSON formatter before production.
- **Status:** Deferred (post-hackathon).

### L-02 — `onchain_writer.py` is still a stub
- **Impact:** On-chain hash-writing is prepared but not live; the Anchor program is deployed and the PDA derivation is correct, but the IDL-driven instruction build is not wired. See `docs/DEMO_SCRIPT.md` for the narrative.
- **Status:** Known, tracked. The registry program itself is fully hardened and ready; the Python writer can be completed with `anchorpy` once the TS IDL is regenerated.

---

## Secrets hygiene (action required by user)

- ⚠️ The real `ANTHROPIC_API_KEY`, `HELIUS_RPC_URL` key, and `TELEGRAM_BOT_TOKEN` were visible in the local `.env`. These were **not** committed (verified: `git log --all --full-history -- .env` returns empty), but since the values were shared in chat, rotate them before recording any public demo:
  - Regenerate the Anthropic key at console.anthropic.com
  - Regenerate the Helius RPC key at dev.helius.xyz
  - Revoke the Telegram bot token via `@BotFather` → `/revoke`
- After rotation, update `.env` and redeploy the backend. The Vercel-hosted frontend does not require changes (no secrets embedded).

---

## Solana Foundation audit checklist

| Check                                                                 | Result |
| --------------------------------------------------------------------- | ------ |
| All PDAs derived with explicit seeds + `bumps` validated              | ✅     |
| `has_one` / explicit signer checks on privileged instructions         | ✅     |
| Checked arithmetic on all counters                                    | ✅     |
| Bounded enum inputs                                                   | ✅     |
| Two-step authority handoff                                            | ✅     |
| Emergency pause / circuit breaker                                     | ✅     |
| No unchecked `AccountInfo` in instruction contexts                    | ✅     |
| No arbitrary CPI surface                                              | ✅ (no CPIs)    |
| Event emission for every state change                                 | ✅     |
| Rent-reclaim path gated                                               | ✅     |
| Dashboard: CSP + HSTS + frame-ancestors deny                          | ✅     |
| API: rate limit + auth on mutating endpoints                          | ✅     |
| Webhook: HMAC signature validation                                    | ✅     |
| Secrets: `.env` ignored, example file provided                        | ✅     |

---

Last updated: April 2026 · SolGuard v2.0
