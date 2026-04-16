"""
SolGuard — Autonomous AI Sentinel for Solana Program Upgrades
FastAPI agent core: polling loop, webhook ingestion, SSE real-time feed, REST API

Security hardening (audit pass v2):
  - Tight CORS allow-list via SOLGUARD_CORS_ORIGINS
  - Helius webhook HMAC / shared-secret validation via HELIUS_WEBHOOK_SECRET
  - Admin-only /api/trigger-test gated by SOLGUARD_ADMIN_TOKEN
  - In-memory token-bucket rate limiter on public endpoints
  - Bounded SSE client list with automatic reaping
  - Structured JSON error responses — no stack traces in 5xx bodies
  - Security response headers on every reply
"""

from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import os
import secrets
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request, BackgroundTasks, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .watchers.upgrade_authority import (
    get_upgrade_authority,
    check_authority_is_multisig,
    WATCHED_PROGRAMS,
)
from .watchers.nonce_monitor import scan_all_authorities as scan_nonce_activity
from .claude_engine import analyze_event
from .database import Database, AlertRecord
from .metrics import alerts_total, programs_monitored, upgrade_events

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
POLL_INTERVAL = max(5, int(os.getenv("POLL_INTERVAL", "30")))
MAX_SSE_CLIENTS = int(os.getenv("MAX_SSE_CLIENTS", "200"))

HELIUS_WEBHOOK_SECRET = os.getenv("HELIUS_WEBHOOK_SECRET", "")
SOLGUARD_ADMIN_TOKEN = os.getenv("SOLGUARD_ADMIN_TOKEN", "")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "SOLGUARD_CORS_ORIGINS",
        "https://solguard.vercel.app,http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if o.strip()
]

# ── In-memory state ──────────────────────────────────────────────────────────
authority_cache: dict[str, str] = {}
sse_clients: list[asyncio.Queue] = []
db = Database()
BOOT_TIME = time.time()

# ── Simple token-bucket rate limiter ─────────────────────────────────────────
_rate_buckets: dict[str, deque] = {}


def _rate_limit(key: str, limit: int = 30, window_s: int = 60) -> bool:
    """Return True if request is allowed; False if rate-limited."""
    now = time.time()
    bucket = _rate_buckets.setdefault(key, deque())
    while bucket and bucket[0] < now - window_s:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def _client_ip(req: Request) -> str:
    # Respect X-Forwarded-For first hop (Vercel, nginx, etc.)
    fwd = req.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else "unknown"


# ── SSE broadcaster ──────────────────────────────────────────────────────────
async def broadcast_event(event_data: dict):
    """Push event to all connected SSE clients. Reap dead/full queues."""
    message = f"data: {json.dumps(event_data)}\n\n"
    disconnected: list[asyncio.Queue] = []
    for q in sse_clients:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            disconnected.append(q)
    for q in disconnected:
        try:
            sse_clients.remove(q)
        except ValueError:
            pass


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🛡️  SolGuard agent starting...")
    if not SOLGUARD_ADMIN_TOKEN:
        print("  ⚠️  SOLGUARD_ADMIN_TOKEN is empty — /api/trigger-test is disabled.")
    if not HELIUS_WEBHOOK_SECRET:
        print("  ⚠️  HELIUS_WEBHOOK_SECRET is empty — /webhooks/helius is anonymous-accepting.")
    db.init()
    programs_monitored.set(len(WATCHED_PROGRAMS))
    poll_task = asyncio.create_task(poll_loop())
    yield
    poll_task.cancel()
    print("🛡️  SolGuard agent shutting down.")


app = FastAPI(
    title="SolGuard",
    description="Autonomous AI Sentinel monitoring Solana program upgrade authority changes in real time.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,  # Safer default; flip to True only if using cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token", "X-Helius-Signature", "ngrok-skip-browser-warning"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.middleware("http")
async def rate_limit_mw(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/webhooks/"):
        ip = _client_ip(request)
        # /webhooks/helius gets a higher bucket; /api gets moderate.
        limit = 120 if path.startswith("/webhooks/") else 60
        if not _rate_limit(f"{ip}:{path}", limit=limit, window_s=60):
            return JSONResponse(status_code=429, content={"error": "rate_limited"})
    return await call_next(request)


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    uptime_s = int(time.time() - BOOT_TIME)
    try:
        stats = db.get_stats()
    except Exception:
        stats = {"total": 0}
    return {
        "status": "ok",
        "version": app.version,
        "watched_programs": len(WATCHED_PROGRAMS),
        "cached_authorities": sum(1 for k in authority_cache if not k.startswith("_")),
        "alerts_recorded": stats.get("total", 0),
        "uptime_seconds": uptime_s,
        "security": {
            "helius_webhook_auth": bool(HELIUS_WEBHOOK_SECRET),
            "admin_endpoints_gated": bool(SOLGUARD_ADMIN_TOKEN),
            "cors_origins": CORS_ORIGINS,
        },
    }


# ── Watchlist endpoint ───────────────────────────────────────────────────────
@app.get("/api/watchlist")
async def get_watchlist():
    programs = []
    for name, pid in WATCHED_PROGRAMS.items():
        authority = authority_cache.get(pid, "loading...")
        programs.append({
            "name": name,
            "program_id": pid,
            "authority": authority,
            "is_immutable": authority == "IMMUTABLE",
        })
    return {"programs": programs, "total": len(programs)}


# ── Alerts history endpoint ──────────────────────────────────────────────────
@app.get("/api/alerts")
async def get_alerts(limit: int = 50, risk_level: str | None = None):
    # Clamp limit to sane range
    limit = max(1, min(500, limit))
    if risk_level and risk_level.upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        raise HTTPException(status_code=400, detail="invalid risk_level")
    alerts = db.get_alerts(limit=limit, risk_level=risk_level.upper() if risk_level else None)
    return {"alerts": [a.__dict__ for a in alerts], "total": len(alerts)}


# ── Stats endpoint ───────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    stats = db.get_stats()
    return {
        "total_alerts": stats["total"],
        "critical": stats["critical"],
        "high": stats["high"],
        "medium": stats["medium"],
        "low": stats["low"],
        "programs_monitored": len(WATCHED_PROGRAMS),
        "last_poll": authority_cache.get("_last_poll", "never"),
    }


# ── Timeline for dashboard sparkline ─────────────────────────────────────────
@app.get("/api/timeline")
async def get_timeline(hours: int = 24):
    """Returns bucketed alert counts per hour for the last `hours` hours."""
    hours = max(1, min(168, hours))
    return db.get_timeline(hours=hours)


# ── SSE stream ───────────────────────────────────────────────────────────────
@app.get("/api/stream")
async def event_stream():
    if len(sse_clients) >= MAX_SSE_CLIENTS:
        raise HTTPException(status_code=503, detail="too many streaming clients")
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_clients.append(queue)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield message
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                sse_clients.remove(queue)
            except ValueError:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Manual trigger (demo/testing) — ADMIN ONLY ───────────────────────────────
@app.post("/api/trigger-test")
async def trigger_test(
    background_tasks: BackgroundTasks,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    if not SOLGUARD_ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="admin endpoint disabled (no token configured)")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, SOLGUARD_ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="invalid admin token")

    fake_event = {
        "type": "SET_AUTHORITY",
        "program_id": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
        "old_authority": "BQ72nSv9f3PRyRKCBnHLVrerrv37CYTHm5h3s9VSGQDV",
        "new_authority": "UnknownWa11etXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        "tx_signature": f"SIM_{uuid.uuid4().hex[:16]}",
        "slot": 999999999,
    }
    background_tasks.add_task(process_event, fake_event)
    return {"status": "test event queued", "event": fake_event}


# ── Public demo endpoint — safe, rate-limited, always mock ───────────────────
@app.post("/api/replay/drift")
async def replay_drift(background_tasks: BackgroundTasks):
    """
    Replays the Drift Protocol attack pattern (April 1, 2026) as a sequence
    of events. Public on purpose: this is how judges / visitors experience
    the product end-to-end without an admin token.
    """
    scenario = [
        {
            "type": "DURABLE_NONCE_ACTIVITY",
            "program_id": "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",
            "old_authority": "",
            "new_authority": "",
            "tx_signature": f"REPLAY_{uuid.uuid4().hex[:16]}",
            "slot": 0,
            "risk_note": "STAGE 1: durable nonce account created near Drift authority.",
            "replay": True,
        },
        {
            "type": "MULTISIG_THRESHOLD_CHANGE",
            "program_id": "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",
            "old_authority": "squads_old_4of7",
            "new_authority": "squads_new_2of5_no_timelock",
            "tx_signature": f"REPLAY_{uuid.uuid4().hex[:16]}",
            "slot": 0,
            "replay": True,
        },
        {
            "type": "SET_AUTHORITY",
            "program_id": "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",
            "old_authority": "squads_new_2of5_no_timelock",
            "new_authority": "UnknownWa11etXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "tx_signature": f"REPLAY_{uuid.uuid4().hex[:16]}",
            "slot": 0,
            "replay": True,
        },
    ]
    for i, ev in enumerate(scenario):
        # Stagger so the dashboard animates the sequence
        background_tasks.add_task(_delayed_process, ev, delay=i * 2.5)
    return {"status": "drift replay queued", "steps": len(scenario)}


async def _delayed_process(event: dict, delay: float):
    await asyncio.sleep(delay)
    await process_event(event)


# ── Helius webhook receiver — authenticated ──────────────────────────────────
@app.post("/webhooks/helius")
async def handle_helius(
    request: Request,
    background_tasks: BackgroundTasks,
    x_helius_signature: str | None = Header(default=None, alias="X-Helius-Signature"),
    authorization: str | None = Header(default=None),
):
    raw = await request.body()

    # ── Authentication ───────────────────────────────────────────────
    if HELIUS_WEBHOOK_SECRET:
        ok = False
        # Accept either:
        #   1. HMAC-SHA256 signature header
        #   2. `Authorization: Bearer <secret>`
        if x_helius_signature:
            expected = hmac.new(
                HELIUS_WEBHOOK_SECRET.encode(),
                raw,
                hashlib.sha256,
            ).hexdigest()
            ok = hmac.compare_digest(expected, x_helius_signature)
        if not ok and authorization:
            prefix = "Bearer "
            if authorization.startswith(prefix):
                ok = hmac.compare_digest(authorization[len(prefix):], HELIUS_WEBHOOK_SECRET)
        if not ok:
            raise HTTPException(status_code=401, detail="invalid webhook signature")

    try:
        payload = json.loads(raw.decode() or "{}")
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})

    transactions = payload if isinstance(payload, list) else [payload]
    queued = 0

    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        tx_type = tx.get("type", "")
        if tx_type in {"UPGRADE", "INITIALIZE_BUFFER", "SET_AUTHORITY"}:
            upgrade_events.inc()
            event = {
                "type": tx_type,
                "program_id": extract_program_id(tx),
                "old_authority": tx.get("metadata", {}).get("oldAuthority"),
                "new_authority": tx.get("metadata", {}).get("newAuthority"),
                "tx_signature": tx.get("signature", "unknown"),
                "slot": tx.get("slot", 0),
            }
            background_tasks.add_task(process_event, event)
            queued += 1

    return {"status": "ok", "processed": len(transactions), "queued_alerts": queued}


# ── Core event processor ─────────────────────────────────────────────────────
async def process_event(event: dict):
    print(f"\n⚡ Event detected: {event.get('type','UNKNOWN')} on {str(event.get('program_id',''))[:20]}...")

    alert = await analyze_event(event)

    risk = alert.get("risk_level", "UNKNOWN")
    alerts_total.labels(risk_level=risk).inc()

    record = AlertRecord(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        program_id=event.get("program_id", "unknown"),
        program_name=_resolve_program_name(event.get("program_id", "")),
        event_type=event.get("type", "UNKNOWN"),
        risk_level=risk,
        summary=alert.get("summary", ""),
        details=alert.get("details", ""),
        recommended_action=alert.get("recommended_action", ""),
        old_authority=event.get("old_authority", "") or "",
        new_authority=event.get("new_authority", "") or "",
        tx_signature=event.get("tx_signature", "") or "",
        source=alert.get("source", "unknown"),
    )
    db.save_alert(record)

    print(f"🔍 Claude assessment: {risk} — {alert.get('summary', 'no summary')}")

    await broadcast_event({"type": "alert", "alert": record.__dict__})

    if DISCORD_WEBHOOK_URL and not DISCORD_WEBHOOK_URL.startswith("your_"):
        await post_discord_alert(alert)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        await post_telegram_alert(alert)

    return alert


# ── Polling loop ─────────────────────────────────────────────────────────────
async def poll_loop():
    from solana.rpc.async_api import AsyncClient

    rpc_url = os.getenv("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
    client = AsyncClient(rpc_url)

    print(f"🔭 Polling {len(WATCHED_PROGRAMS)} programs every {POLL_INTERVAL}s...")
    consecutive_failures = 0

    while True:
        try:
            for name, program_id in WATCHED_PROGRAMS.items():
                try:
                    authority = await get_upgrade_authority(client, program_id)
                    prev = authority_cache.get(program_id)

                    if prev is None:
                        authority_cache[program_id] = authority
                        display = (authority[:20] + "...") if authority and authority != "IMMUTABLE" else (authority or "unknown")
                        print(f"  ✅ {name}: authority = {display}")
                        continue
                    elif prev != authority:
                        print(f"  🚨 AUTHORITY CHANGE on {name}!")
                        upgrade_events.inc()
                        multisig_info = await check_authority_is_multisig(client, authority) if authority else {}
                        event = {
                            "type": "SET_AUTHORITY",
                            "program_id": program_id,
                            "old_authority": prev,
                            "new_authority": authority,
                            "new_authority_is_multisig": multisig_info.get("is_multisig", False),
                            "tx_signature": "detected_via_polling",
                            "slot": 0,
                        }
                        authority_cache[program_id] = authority
                        await process_event(event)

                except Exception as e:
                    print(f"  ⚠️  Error polling {name}: {e}")

            authority_cache["_last_poll"] = datetime.now(timezone.utc).isoformat()

            await broadcast_event({
                "type": "watchlist_update",
                "programs": [
                    {
                        "name": name,
                        "program_id": pid,
                        "authority": authority_cache.get(pid, "unknown"),
                        "is_immutable": authority_cache.get(pid) == "IMMUTABLE",
                    }
                    for name, pid in WATCHED_PROGRAMS.items()
                ],
            })

            # ── Durable nonce scan (every 5th cycle) ───────────────
            poll_count = getattr(poll_loop, "_count", 0) + 1
            poll_loop._count = poll_count

            if poll_count % 5 == 0:
                try:
                    print("🔍 Scanning for durable nonce activity (Drift attack pattern)...")
                    nonce_events = await scan_nonce_activity(client, authority_cache, WATCHED_PROGRAMS)
                    for ne in nonce_events:
                        print(f"  🚨 NONCE ACTIVITY: {ne['program_name']}")
                        await process_event({
                            "type": "DURABLE_NONCE_ACTIVITY",
                            "program_id": ne.get("authority", "unknown"),
                            "old_authority": "",
                            "new_authority": "",
                            "tx_signature": ne.get("tx_signature", "unknown"),
                            "slot": ne.get("slot", 0),
                            "risk_note": ne.get("risk_note", ""),
                        })
                    if not nonce_events:
                        print("  ✅ No suspicious nonce activity")
                except Exception as e:
                    print(f"  ⚠️  Nonce scan error: {e}")

            consecutive_failures = 0

        except Exception as e:
            consecutive_failures += 1
            print(f"  ⚠️  Poll cycle failed (#{consecutive_failures}): {e}")
            # Exponential backoff if RPC is flaking — up to 5 min
            await asyncio.sleep(min(300, POLL_INTERVAL * (2 ** min(consecutive_failures, 4))))
            continue

        await asyncio.sleep(POLL_INTERVAL)


# ── Discord notification ─────────────────────────────────────────────────────
async def post_discord_alert(alert: dict):
    risk = alert.get("risk_level", "UNKNOWN")
    color_map = {"LOW": 3066993, "MEDIUM": 16776960, "HIGH": 15158332, "CRITICAL": 10038562}
    emoji_map = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}

    embed = {
        "title": f"🛡️ SolGuard Alert — {emoji_map.get(risk, '⚪')} {risk}",
        "description": alert.get("summary", "No summary"),
        "color": color_map.get(risk, 8421504),
        "fields": [
            {"name": "Program", "value": f"`{alert.get('program_id', 'unknown')[:44]}`", "inline": False},
            {"name": "Details", "value": (alert.get("details", "N/A") or "N/A")[:300], "inline": False},
            {"name": "Recommended Action", "value": alert.get("recommended_action", "Monitor closely"), "inline": False},
            {"name": "Source", "value": f"`{alert.get('source', 'unknown')}`", "inline": True},
        ],
        "footer": {"text": "SolGuard Sentinel • Powered by Claude AI"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as http:
            await http.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"  Discord notify failed: {e}")


# ── Telegram notification ────────────────────────────────────────────────────
async def post_telegram_alert(alert: dict):
    risk = alert.get("risk_level", "UNKNOWN")
    emoji_map = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}

    text = (
        f"{emoji_map.get(risk, '⚪')} *SolGuard Alert — {risk}*\n\n"
        f"{alert.get('summary', 'No summary')}\n\n"
        f"*Program:* `{alert.get('program_id', 'unknown')[:44]}`\n"
        f"*Action:* {alert.get('recommended_action', 'Monitor closely')}\n"
        f"*Source:* {alert.get('source', 'unknown')}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            await http.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            })
    except Exception as e:
        print(f"  Telegram notify failed: {e}")


# ── Helpers ──────────────────────────────────────────────────────────────────
def extract_program_id(tx: dict) -> str:
    accounts = tx.get("accountData", []) or []
    for acc in accounts:
        account_key = acc.get("account") if isinstance(acc, dict) else None
        if account_key and isinstance(account_key, str) and 32 <= len(account_key) <= 44:
            return account_key
    return tx.get("programId", "unknown")


def _resolve_program_name(program_id: str) -> str:
    for name, pid in WATCHED_PROGRAMS.items():
        if pid == program_id:
            return name
    return "Unknown Program"
