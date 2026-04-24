"""
Outbound alert fanout for solguard-core.

Replaces the embedded Telegram/Discord logic that used to live inside
agent/main.py. Core now has zero knowledge of specific channels — it just
HMAC-signs each alert and POSTs it to every URL listed in NOTIFIER_URLS.

The private solguard-notifiers service (or any third-party integration)
receives the payload, verifies the signature, and fans out to whatever
channels the operator configures there.

Environment:
  NOTIFIER_URLS           Comma-separated list of webhook URLs (optional)
  NOTIFIER_HMAC_SECRET    Shared secret for HMAC-SHA256 signing (required
                          if NOTIFIER_URLS is set)
  NOTIFIER_TIMEOUT_S      Request timeout per URL (default: 5s)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from typing import Iterable

import httpx

NOTIFIER_URLS: list[str] = [
    u.strip() for u in os.getenv("NOTIFIER_URLS", "").split(",") if u.strip()
]
NOTIFIER_HMAC_SECRET: str = os.getenv("NOTIFIER_HMAC_SECRET", "")
NOTIFIER_TIMEOUT_S: float = float(os.getenv("NOTIFIER_TIMEOUT_S", "5"))


def _sign(body: bytes, ts: str) -> str:
    """Compute HMAC-SHA256 over `ts.body` — like Stripe webhook signing."""
    if not NOTIFIER_HMAC_SECRET:
        return ""
    mac = hmac.new(
        NOTIFIER_HMAC_SECRET.encode("utf-8"),
        f"{ts}.".encode("utf-8") + body,
        hashlib.sha256,
    )
    return mac.hexdigest()


async def _post_one(client: httpx.AsyncClient, url: str, body: bytes, ts: str, sig: str) -> None:
    try:
        await client.post(
            url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-SolGuard-Timestamp": ts,
                "X-SolGuard-Signature": sig,
                "User-Agent": "solguard-core/2.0",
            },
            timeout=NOTIFIER_TIMEOUT_S,
        )
    except Exception as e:
        # Intentionally log-only. Notifier failures must never crash core.
        print(f"  Notifier POST to {url} failed: {e}")


async def fanout_alert(alert: dict) -> None:
    """Fan out an alert payload to every configured notifier URL."""
    if not NOTIFIER_URLS:
        return
    if not NOTIFIER_HMAC_SECRET:
        print("  ⚠️  NOTIFIER_URLS set but NOTIFIER_HMAC_SECRET missing — refusing to send unsigned alerts")
        return

    body = json.dumps(alert, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ts = str(int(time.time()))
    sig = _sign(body, ts)

    async with httpx.AsyncClient() as client:
        await asyncio.gather(
            *(_post_one(client, url, body, ts, sig) for url in NOTIFIER_URLS),
            return_exceptions=True,
        )


def verify_signature(body: bytes, ts_header: str, sig_header: str, max_age_s: int = 300) -> bool:
    """Convenience helper for any receiver (tests, custom relays) to validate a payload.

    Ships here so that internal services can import the same logic; solguard-notifiers
    has its own copy for independence.
    """
    if not NOTIFIER_HMAC_SECRET or not ts_header or not sig_header:
        return False
    try:
        ts = int(ts_header)
    except ValueError:
        return False
    if abs(time.time() - ts) > max_age_s:
        return False
    expected = _sign(body, ts_header)
    return hmac.compare_digest(expected, sig_header)
