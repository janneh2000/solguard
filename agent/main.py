"""
SolGuard — Autonomous AI Sentinel for Solana Program Upgrades
FastAPI agent core: polling loop, webhook ingestion, SSE real-time feed, REST API
"""

import asyncio
import os
import json
import time
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .watchers.upgrade_authority import get_upgrade_authority, check_authority_is_multisig, WATCHED_PROGRAMS
from .claude_engine import analyze_event
from .database import Database, AlertRecord
from .metrics import alerts_total, programs_monitored, upgrade_events

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

# ── In-memory state ──────────────────────────────────────────────────────────
authority_cache: dict[str, str] = {}
sse_clients: list[asyncio.Queue] = []
db = Database()


# ── SSE broadcaster ──────────────────────────────────────────────────────────
async def broadcast_event(event_data: dict):
    """Push event to all connected SSE clients."""
    message = f"data: {json.dumps(event_data)}\n\n"
    disconnected = []
    for q in sse_clients:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            disconnected.append(q)
    for q in disconnected:
        sse_clients.remove(q)


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🛡️  SolGuard agent starting...")
    db.init()
    programs_monitored.set(len(WATCHED_PROGRAMS))
    asyncio.create_task(poll_loop())
    yield
    print("🛡️  SolGuard agent shutting down.")


app = FastAPI(
    title="SolGuard",
    description="Autonomous AI Sentinel monitoring Solana program upgrade authority changes in real time.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "watched_programs": len(WATCHED_PROGRAMS),
        "cached_authorities": len(authority_cache),
        "uptime": time.time(),
    }


# ── Watchlist endpoint ───────────────────────────────────────────────────────
@app.get("/api/watchlist")
async def get_watchlist():
    """Returns current watchlist with cached authority info."""
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
    """Returns historical alerts from the database."""
    alerts = db.get_alerts(limit=limit, risk_level=risk_level)
    return {"alerts": [a.__dict__ for a in alerts], "total": len(alerts)}


# ── Stats endpoint ───────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    """Dashboard statistics."""
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


# ── SSE stream ───────────────────────────────────────────────────────────────
@app.get("/api/stream")
async def event_stream():
    """Server-Sent Events stream for real-time dashboard updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_clients.append(queue)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in sse_clients:
                sse_clients.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Manual trigger (demo/testing) ────────────────────────────────────────────
@app.post("/api/trigger-test")
async def trigger_test(background_tasks: BackgroundTasks):
    """Simulates an upgrade authority change for demo purposes."""
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


# ── Helius webhook receiver ──────────────────────────────────────────────────
@app.post("/webhooks/helius")
async def handle_helius(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})

    transactions = payload if isinstance(payload, list) else [payload]
    queued = 0

    for tx in transactions:
        tx_type = tx.get("type", "")
        if tx_type in ["UPGRADE", "INITIALIZE_BUFFER", "SET_AUTHORITY"]:
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
    print(f"\n⚡ Event detected: {event['type']} on {event['program_id'][:20]}...")

    alert = await analyze_event(event)

    risk = alert.get("risk_level", "UNKNOWN")
    alerts_total.labels(risk_level=risk).inc()

    # Persist to database
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
        old_authority=event.get("old_authority", ""),
        new_authority=event.get("new_authority", ""),
        tx_signature=event.get("tx_signature", ""),
        source=alert.get("source", "unknown"),
    )
    db.save_alert(record)

    print(f"🔍 Claude assessment: {risk} — {alert.get('summary', 'no summary')}")

    # Broadcast to SSE clients
    await broadcast_event({
        "type": "alert",
        "alert": record.__dict__,
    })

    # Notify Discord
    if DISCORD_WEBHOOK_URL and DISCORD_WEBHOOK_URL != "your_discord_webhook":
        await post_discord_alert(alert)

    # Notify Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        await post_telegram_alert(alert)

    return alert


# ── Polling loop ─────────────────────────────────────────────────────────────
async def poll_loop():
    from solana.rpc.async_api import AsyncClient

    rpc_url = os.getenv("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
    client = AsyncClient(rpc_url)

    print(f"🔭 Polling {len(WATCHED_PROGRAMS)} programs every {POLL_INTERVAL}s...")

    while True:
        for name, program_id in WATCHED_PROGRAMS.items():
            try:
                authority = await get_upgrade_authority(client, program_id)
                prev = authority_cache.get(program_id)

                if prev is None:
                    authority_cache[program_id] = authority
                    display = authority[:20] + "..." if authority and authority != "IMMUTABLE" else authority or "unknown"
                    print(f"  ✅ {name}: authority = {display}")
                    continue
                elif prev != authority:
                    print(f"  🚨 AUTHORITY CHANGE on {name}!")
                    upgrade_events.inc()

                    # Enrich with Squads multisig detection
                    multisig_info = await check_authority_is_multisig(client, authority)

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

        # Broadcast watchlist update to dashboard
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
            {"name": "Details", "value": alert.get("details", "N/A")[:200], "inline": False},
            {"name": "Recommended Action", "value": alert.get("recommended_action", "Monitor closely"), "inline": False},
            {"name": "Source", "value": f"`{alert.get('source', 'unknown')}`", "inline": True},
        ],
        "footer": {"text": "SolGuard Sentinel • Powered by Claude AI"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient() as http:
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
        async with httpx.AsyncClient() as http:
            await http.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            })
    except Exception as e:
        print(f"  Telegram notify failed: {e}")


# ── Helpers ──────────────────────────────────────────────────────────────────
def extract_program_id(tx: dict) -> str:
    accounts = tx.get("accountData", [])
    for acc in accounts:
        if acc.get("account") and len(acc["account"]) == 44:
            return acc["account"]
    return tx.get("programId", "unknown")


def _resolve_program_name(program_id: str) -> str:
    for name, pid in WATCHED_PROGRAMS.items():
        if pid == program_id:
            return name
    return "Unknown Program"
