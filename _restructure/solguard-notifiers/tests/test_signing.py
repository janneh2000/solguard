"""Signature verification tests for the notifier receiver."""
import hashlib
import hmac
import os
import time

# Must be set BEFORE importing the module under test (module reads env at import).
os.environ["NOTIFIER_HMAC_SECRET"] = "testsecret"
os.environ["MAX_CLOCK_SKEW_S"] = "300"

from src import signing  # noqa: E402


def _sign(body: bytes, ts: str) -> str:
    return hmac.new(
        b"testsecret", f"{ts}.".encode("utf-8") + body, hashlib.sha256
    ).hexdigest()


def test_valid_signature_passes():
    body = b'{"risk_level":"CRITICAL"}'
    ts = str(int(time.time()))
    sig = _sign(body, ts)
    assert signing.verify(body, ts, sig) is True


def test_tampered_body_fails():
    body = b'{"risk_level":"CRITICAL"}'
    ts = str(int(time.time()))
    sig = _sign(body, ts)
    tampered = b'{"risk_level":"LOW"}'
    assert signing.verify(tampered, ts, sig) is False


def test_wrong_secret_fails():
    body = b'{"x":1}'
    ts = str(int(time.time()))
    wrong_sig = hmac.new(b"othersecret", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert signing.verify(body, ts, wrong_sig) is False


def test_stale_timestamp_fails():
    body = b'{"x":1}'
    ts = str(int(time.time()) - 10_000)  # way outside the skew window
    sig = _sign(body, ts)
    assert signing.verify(body, ts, sig) is False


def test_missing_headers_fails():
    body = b'{"x":1}'
    assert signing.verify(body, None, "abc") is False
    assert signing.verify(body, "123", None) is False


def test_non_integer_timestamp_fails():
    body = b'{"x":1}'
    sig = _sign(body, "not-a-number")
    assert signing.verify(body, "not-a-number", sig) is False
