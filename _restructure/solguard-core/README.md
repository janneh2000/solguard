# solguard-core

**Autonomous AI sentinel for Solana program upgrade authorities.** Catches Drift-style hijacks — the kind that drained $285M in ten seconds — before the drain.

This is the **open-source engine**: Solana watchers, the Claude-powered risk scorer, the SQLite alert ledger, and the on-chain registry program. It exposes a REST + SSE API and HMAC-signs every alert it emits, so any downstream notifier or dashboard can subscribe.

For the hosted dashboard and enterprise notifier bots, see the private companion repos (`solguard-dashboard`, `solguard-notifiers`). Core runs standalone — the companions are optional.

---

## Why SolGuard

On April 1st, 2026, DPRK actor UNC4736 drained $285M from Drift Protocol. The exploit wasn't in the smart contracts — it was in the **upgrade authority**. The attacker:
1. Created durable nonce accounts near the Drift authority keypair (pre-signed, timelock-free).
2. Migrated the Security Council multisig to 2-of-5 with zero timelock.
3. Transferred admin authority to a fresh wallet and drained the protocol.

No on-chain tooling flagged it. Post-incident, the mitigation was "rotate everything and hope." SolGuard is the sentinel that would have caught every stage in real time.

## What it does

- Polls upgrade authorities on 15+ top Solana programs every 30s.
- Detects authority changes, durable-nonce activity, and Squads multisig threshold reductions.
- Scores every signal with Claude (Opus / Sonnet 4.6) against a library of known attack patterns: `drift_dprk`, `jito_bundle_upgrade`, `multisig_threshold_reduction`, `generic_authority_hijack`.
- Emits a real-time SSE feed and HMAC-signed webhook alerts.
- Writes a SHA-256 hash of every alert to the on-chain SolGuard Registry (Anchor program on devnet: [`5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM`](https://explorer.solana.com/address/5kkaYGaXECsngVohp3Z7NdDnxpfatTqSsmMVpsnngZFM?cluster=devnet)).

## Quick start

```bash
# Docker (recommended)
cp .env.example .env        # fill in HELIUS_RPC_URL, HELIUS_WEBHOOK_SECRET, etc.
docker build -t solguard-core .
docker run -p 8000:8000 --env-file .env -v solguard-data:/data solguard-core

# Native Python
pip install -r requirements.txt
uvicorn agent.main:app --host 0.0.0.0 --port 8000

# Check it's alive
curl http://localhost:8000/health
```

## API surface

| Endpoint                  | Method | Auth              | Description                              |
|---------------------------|--------|-------------------|------------------------------------------|
| `/health`                 | GET    | none              | Liveness + version                       |
| `/api/alerts`             | GET    | rate-limited      | Paginated alert history                  |
| `/api/stats`              | GET    | rate-limited      | Alert counts by severity                 |
| `/api/timeline`           | GET    | rate-limited      | Hour-bucketed counts for sparkline       |
| `/api/watchlist`          | GET    | rate-limited      | Current authorities on all watched progs |
| `/api/stream`             | GET    | rate-limited      | SSE live feed                            |
| `/api/replay/drift`       | POST   | rate-limited      | Cinematic demo of the Drift hack (3 stages) |
| `/api/trigger-test`       | POST   | `X-Admin-Token`   | Fire a synthetic alert (admin only)      |
| `/webhooks/helius`        | POST   | HMAC-SHA256       | Helius webhook ingress                   |

## Outbound notifications

Core does not ship with Telegram, Discord, or email clients. Instead it **HMAC-signs every alert** and POSTs to each URL in `NOTIFIER_URLS`. Any compatible receiver works — including the sister [solguard-notifiers](../solguard-notifiers) service, which ships Telegram + Discord clients out of the box.

Signature format (inspired by Stripe):

```
X-SolGuard-Timestamp: 1714032000
X-SolGuard-Signature: <hex HMAC-SHA256 of "timestamp." + body using NOTIFIER_HMAC_SECRET>
```

Verify with `agent.notifiers.verify_signature(body, ts_header, sig_header)` or the equivalent 10-line function in your own language.

## Running the tests

```bash
pip install pytest
pytest agent/tests/ -v
```

13 tests currently green (9 risk-engine, 4 database).

## Architecture

```
Helius webhooks ┐
                ├─► poll_loop + watchers ─► claude_engine ─► Database
Solana RPC ─────┘                                    │
                                                     ├─► SSE broadcast
                                                     ├─► on-chain registry (sha256)
                                                     └─► fanout_alert (HMAC) ─► NOTIFIER_URLS
```

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). New detectors, attack-pattern fingerprints, and chain adapters welcome.

## License

MIT. See [LICENSE](./LICENSE).
