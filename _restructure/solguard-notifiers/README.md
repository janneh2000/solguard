# solguard-notifiers

**Private.** HMAC-authenticated alert fanout for SolGuard — ships Telegram and Discord out of the box. Add new channels by dropping a client module into `src/`.

This service is deliberately independent of `solguard-core`: the only contract is the HTTP wire format. Any compatible sender can post here; this receiver can run anywhere.

---

## Wire format

Core (or any compatible sender) makes a request:

```
POST /alert
Content-Type: application/json
X-SolGuard-Timestamp: 1714032000
X-SolGuard-Signature: <hex HMAC-SHA256 of "{timestamp}." + body, keyed by NOTIFIER_HMAC_SECRET>

{
  "id": "...",
  "risk_level": "CRITICAL",
  "summary": "...",
  "details": "...",
  "program_id": "...",
  "recommended_action": "...",
  "source": "helius|poller|mock"
}
```

We reject anything:
- without valid headers,
- with a timestamp older than `MAX_CLOCK_SKEW_S` (default 300s) — replay defense,
- whose HMAC does not match.

## Running

```bash
cp .env.example .env   # fill in NOTIFIER_HMAC_SECRET + channel creds

# Docker
docker build -t solguard-notifiers .
docker run -p 8001:8001 --env-file .env solguard-notifiers

# Native
pip install -r requirements.txt
uvicorn src.server:app --host 0.0.0.0 --port 8001
```

## Health check

```bash
curl http://localhost:8001/health
# {"status":"ok","version":"1.0.0","channels":{"telegram_client":true,"discord_client":false}}
```

## Adding a new channel

1. Write `src/<name>_client.py` exposing `is_configured() -> bool` and `async def send(alert: dict) -> None`.
2. Import + append it to `CHANNELS` in `src/server.py`.
3. Rebuild. Done.

Candidates on the roadmap: Slack, PagerDuty, email, SMS (Twilio), on-chain multisig proposal, Apple Push.

## Why a separate service?

- **Core stays auditable.** The public open-source engine knows nothing about private channel secrets.
- **Scale independently.** If Discord rate-limits, your core polling loop isn't affected.
- **Per-customer isolation.** Enterprise deployments run their own notifier with their own keys.
- **Plug-in architecture.** Adding a channel is a single-file PR in a private repo — no churn in the public engine.

## Tests

```bash
pip install pytest
pytest tests/ -v
```
