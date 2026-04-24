"""Discord client — extracted from solguard-core/agent/main.py."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
TIMEOUT_S: float = float(os.getenv("DISCORD_TIMEOUT_S", "10"))

COLOR = {"LOW": 3066993, "MEDIUM": 16776960, "HIGH": 15158332, "CRITICAL": 10038562}
EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}


def is_configured() -> bool:
    return bool(DISCORD_WEBHOOK_URL) and not DISCORD_WEBHOOK_URL.startswith("your_")


async def send(alert: dict) -> None:
    if not is_configured():
        return
    risk = alert.get("risk_level", "UNKNOWN")
    embed = {
        "title": f"🛡️ SolGuard Alert — {EMOJI.get(risk, '⚪')} {risk}",
        "description": alert.get("summary", "No summary"),
        "color": COLOR.get(risk, 8421504),
        "fields": [
            {"name": "Program", "value": f"`{(alert.get('program_id') or 'unknown')[:44]}`", "inline": False},
            {"name": "Details", "value": (alert.get("details", "N/A") or "N/A")[:300], "inline": False},
            {"name": "Recommended Action", "value": alert.get("recommended_action", "Monitor closely"), "inline": False},
            {"name": "Source", "value": f"`{alert.get('source', 'unknown')}`", "inline": True},
        ],
        "footer": {"text": "SolGuard Sentinel • Powered by Claude AI"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as http:
            await http.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"  Discord notify failed: {e}")
