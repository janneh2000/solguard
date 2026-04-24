"""HMAC signature verification for alerts inbound from solguard-core.

Keeps its own copy intentionally — notifiers must not depend on the core
package at runtime, only on the HTTP contract.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

NOTIFIER_HMAC_SECRET: str = os.getenv("NOTIFIER_HMAC_SECRET", "")
MAX_CLOCK_SKEW_S: int = int(os.getenv("MAX_CLOCK_SKEW_S", "300"))


def _expected_signature(body: bytes, ts: str) -> str:
    mac = hmac.new(
        NOTIFIER_HMAC_SECRET.encode("utf-8"),
        f"{ts}.".encode("utf-8") + body,
        hashlib.sha256,
    )
    return mac.hexdigest()


def verify(body: bytes, ts_header: str | None, sig_header: str | None) -> bool:
    """Return True iff the request is within the skew window and HMAC matches."""
    if not NOTIFIER_HMAC_SECRET:
        # Fail-closed: in production a missing secret is a config error.
        return False
    if not ts_header or not sig_header:
        return False
    try:
        ts = int(ts_header)
    except ValueError:
        return False
    if abs(time.time() - ts) > MAX_CLOCK_SKEW_S:
        return False
    expected = _expected_signature(body, ts_header)
    return hmac.compare_digest(expected, sig_header)
