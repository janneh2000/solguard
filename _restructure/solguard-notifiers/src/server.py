"""
solguard-notifiers — HMAC-authenticated alert receiver.

Core POSTs every alert here as JSON with X-SolGuard-Timestamp and
X-SolGuard-Signature headers. We verify, then fan out to whichever
downstream channel clients (Telegram, Discord, ...) are configured.

Add new channels by writing another client module and appending it to
the CHANNELS list below. No other wiring required.
"""
from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from . import discord_client, telegram_client
from .signing import verify

AppLifespanFn = Callable[[FastAPI], Awaitable[None]]

app = FastAPI(
    title="solguard-notifiers",
    version="1.0.0",
    description="HMAC-authenticated alert fanout for SolGuard.",
)

# Register channels here. Each must expose `async def send(alert: dict) -> None`
# and `def is_configured() -> bool`.
CHANNELS = [telegram_client, discord_client]


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": app.version,
        "channels": {c.__name__.rsplit(".", 1)[-1]: c.is_configured() for c in CHANNELS},
    }


@app.post("/alert")
async def ingest_alert(
    request: Request,
    x_solguard_timestamp: str | None = Header(default=None),
    x_solguard_signature: str | None = Header(default=None),
) -> JSONResponse:
    body = await request.body()

    if not verify(body, x_solguard_timestamp, x_solguard_signature):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        import json

        alert = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json")

    # Fire-and-forget fanout so the HTTP response isn't blocked on slow channels.
    tasks = [c.send(alert) for c in CHANNELS if c.is_configured()]
    # Run with a timeout so a hanging channel can't starve the event loop.
    if tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=15)
        except asyncio.TimeoutError:
            pass  # individual channels already log their own failures

    return JSONResponse({"ok": True, "delivered": len(tasks)})
