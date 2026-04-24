"""Telegram client — extracted from solguard-core/agent/main.py."""
from __future__ import annotations

import os

import httpx

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
TIMEOUT_S: float = float(os.getenv("TELEGRAM_TIMEOUT_S", "10"))

EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}


def is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


async def send(alert: dict) -> None:
    if not is_configured():
        return
    risk = alert.get("risk_level", "UNKNOWN")
    text = (
        f"{EMOJI.get(risk, '⚪')} *SolGuard Alert — {risk}*\n\n"
        f"{alert.get('summary', 'No summary')}\n\n"
        f"*Program:* `{(alert.get('program_id') or 'unknown')[:44]}`\n"
        f"*Action:* {alert.get('recommended_action', 'Monitor closely')}\n"
        f"*Source:* {alert.get('source', 'unknown')}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as http:
            await http.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
    except Exception as e:
        print(f"  Telegram notify failed: {e}")
