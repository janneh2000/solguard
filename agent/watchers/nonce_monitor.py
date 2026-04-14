"""
SolGuard — Durable Nonce Monitor
Detects durable nonce account activity targeting watched program authorities.

CONTEXT: In the Drift Protocol hack (April 1, 2026), DPRK attackers used Solana's
durable nonce feature to pre-sign admin transfer transactions days before execution.
The pre-signed transactions were triggered on April 1, draining $285M in 10 seconds.

This module monitors for suspicious durable nonce activity around watched authorities.
"""

import asyncio
import os
from datetime import datetime, timezone
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from dotenv import load_dotenv

load_dotenv()

# Solana System Program nonce instruction discriminators
NONCE_PROGRAM = "11111111111111111111111111111111"
NONCE_INITIALIZE_IX = 6  # InitializeNonceAccount instruction index
NONCE_ADVANCE_IX = 4     # AdvanceNonceAccount instruction index
NONCE_AUTHORIZE_IX = 7   # AuthorizeNonceAccount instruction index


async def check_nonce_activity(
    client: AsyncClient,
    authority_address: str,
    program_name: str,
) -> list[dict]:
    """
    Check for recent durable nonce accounts associated with a program authority.

    Returns a list of suspicious nonce events if found. These events should be
    fed into the risk engine for scoring.

    This detects the Drift attack pattern:
    1. Attacker creates durable nonce accounts
    2. Gets multisig signers to pre-sign transactions
    3. Triggers the pre-signed transactions later
    """
    if not authority_address or authority_address in ("IMMUTABLE", "unknown"):
        return []

    suspicious_events = []

    try:
        authority_pubkey = Pubkey.from_string(authority_address)

        # Check recent transactions involving this authority
        # Look for nonce-related instructions
        sigs_response = await client.get_signatures_for_address(
            authority_pubkey,
            limit=20,
        )

        if not sigs_response.value:
            return []

        for sig_info in sigs_response.value:
            # Check if this transaction involves nonce operations
            # by fetching the full transaction
            try:
                tx_response = await client.get_transaction(
                    sig_info.signature,
                    max_supported_transaction_version=0,
                )

                if not tx_response.value:
                    continue

                tx = tx_response.value.transaction
                meta = tx_response.value.transaction.meta

                # Look for nonce-related program invocations in the logs
                if meta and meta.log_messages:
                    logs = meta.log_messages
                    has_nonce_activity = any(
                        "AdvanceNonceAccount" in log or
                        "InitializeNonceAccount" in log or
                        "AuthorizeNonceAccount" in log
                        for log in logs
                    )

                    if has_nonce_activity:
                        suspicious_events.append({
                            "type": "DURABLE_NONCE_ACTIVITY",
                            "program_name": program_name,
                            "authority": authority_address,
                            "tx_signature": str(sig_info.signature),
                            "slot": sig_info.slot,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "risk_note": (
                                "Durable nonce activity detected near program authority. "
                                "This is the same technique used in the Drift Protocol hack "
                                "(April 2026, $285M stolen). Durable nonces allow transactions "
                                "to be pre-signed and executed later — a key staging step in "
                                "social engineering attacks on multisig signers."
                            ),
                        })

            except Exception:
                # Skip transactions we can't parse
                continue

    except Exception as e:
        print(f"  ⚠️  Nonce check error for {program_name}: {e}")

    return suspicious_events


async def scan_all_authorities(
    client: AsyncClient,
    authority_cache: dict,
    watched_programs: dict,
) -> list[dict]:
    """
    Scan all cached authorities for durable nonce activity.
    Returns a list of suspicious events across all watched programs.
    """
    all_events = []

    for name, program_id in watched_programs.items():
        authority = authority_cache.get(program_id)
        if authority and authority not in ("IMMUTABLE", "unknown", "_last_poll"):
            events = await check_nonce_activity(client, authority, name)
            all_events.extend(events)

    return all_events


# ── Quick test ────────────────────────────────────────────────────────────────
async def _test():
    from .upgrade_authority import WATCHED_PROGRAMS

    rpc = os.getenv("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
    client = AsyncClient(rpc)

    print(f"\n🔍 SolGuard — Scanning for durable nonce activity\n{'─'*60}")

    # Test with Jupiter's authority
    events = await check_nonce_activity(
        client,
        "CvQZZ23qYDWF2RUpxYJ8y9K4skmuvYEEjH7fK58jtipQ",
        "Jupiter v6",
    )

    if events:
        for e in events:
            print(f"  🚨 {e['type']} on {e['program_name']}: {e['tx_signature'][:20]}...")
    else:
        print("  ✅ No suspicious nonce activity detected")

    await client.close()
    print(f"{'─'*60}\n")

if __name__ == "__main__":
    asyncio.run(_test())
