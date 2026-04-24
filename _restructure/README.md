# SolGuard → 3-Repo Restructure (Staging)

This directory is a **staging ground**. Nothing here is live yet — your production repo at `~/Desktop/solguard/` is untouched and remains your Phase 3 submission snapshot.

## What's inside

```
_restructure/
├── solguard-core/          → github.com/janneh2000/solguard-core     (public)
├── solguard-dashboard/     → github.com/janneh2000/solguard-dashboard (private)
├── solguard-notifiers/     → github.com/janneh2000/solguard-notifiers (private)
├── docker-compose.yml      → runs all three locally for dev
└── MIGRATION.md            → step-by-step push + deploy guide
```

## Order of operations

1. **Finish Phase 3 first.** Record the video using the current monorepo. Do not touch this folder until your submission is in.
2. **Tag the submission.** `git tag -a phase3-submission -m "Phase 3 final" && git push --tags` from `~/Desktop/solguard/`. This is the rollback point.
3. **Follow `MIGRATION.md`.** It walks through creating the three GitHub repos, copying files out of `_restructure/`, pushing, and redeploying.

## Architecture

```
┌─────────────────────┐        SSE stream         ┌─────────────────────┐
│  solguard-dashboard │ ◄──────────────────────── │   solguard-core     │
│  (static HTML, nginx│                           │  (FastAPI + Anchor) │
│   or Vercel)        │                           │                     │
└─────────────────────┘                           │  - watchers/        │
                                                  │  - claude_engine    │
                                                  │  - database         │
                                                  │  - onchain_writer   │
                                                  │  - webhook fanout ──┼──┐
                                                  └─────────────────────┘  │
                                                                           │ HMAC-signed POST
                                                                           ▼
                                                          ┌─────────────────────┐
                                                          │ solguard-notifiers  │
                                                          │ (FastAPI receiver)  │
                                                          │   - Telegram        │
                                                          │   - Discord         │
                                                          │   - future: SMS,    │
                                                          │     email, Slack    │
                                                          └─────────────────────┘
```

**Why this split**
- `solguard-core` stays open-source and auditable. It knows nothing about private channels.
- `solguard-notifiers` holds business logic (per-customer channels, rate tiers, enterprise SLAs). Stays private.
- `solguard-dashboard` is the UI and can be swapped/rebranded per customer. Stays private.

The three services talk over HTTP with HMAC-signed payloads. No code coupling.
