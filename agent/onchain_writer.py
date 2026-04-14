"""
SolGuard — On-Chain Alert Writer
Submits alert hashes to the SolGuard Registry Anchor program on Solana.
This creates an immutable, verifiable record of every detected event.
"""

import os
import json
import hashlib
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solana.rpc.async_api import AsyncClient
from dotenv import load_dotenv

load_dotenv()

# Program ID — update after `anchor deploy`
REGISTRY_PROGRAM_ID = os.getenv(
    "SOLGUARD_PROGRAM_ID",
    "SGRDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
)

RISK_LEVEL_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
EVENT_TYPE_MAP = {"SET_AUTHORITY": 0, "UPGRADE": 1, "INITIALIZE_BUFFER": 2}


def compute_alert_hash(alert: dict) -> bytes:
    """
    Compute SHA-256 hash of alert data for on-chain storage.
    The hash can be used to verify that the on-chain record matches
    the full off-chain alert stored in the database.
    """
    # Deterministic JSON serialization
    canonical = json.dumps({
        "program_id": alert.get("program_id", ""),
        "risk_level": alert.get("risk_level", ""),
        "event_type": alert.get("event_type", ""),
        "summary": alert.get("summary", ""),
        "old_authority": alert.get("old_authority", ""),
        "new_authority": alert.get("new_authority", ""),
        "tx_signature": alert.get("tx_signature", ""),
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).digest()


def derive_registry_pda() -> tuple[Pubkey, int]:
    """Derive the registry PDA."""
    program_id = Pubkey.from_string(REGISTRY_PROGRAM_ID)
    return Pubkey.find_program_address([b"registry"], program_id)


def derive_alert_pda(alert_index: int) -> tuple[Pubkey, int]:
    """Derive the alert PDA for a given index."""
    program_id = Pubkey.from_string(REGISTRY_PROGRAM_ID)
    return Pubkey.find_program_address(
        [b"alert", alert_index.to_bytes(8, "little")],
        program_id,
    )


async def write_alert_onchain(alert: dict, alert_index: int) -> str | None:
    """
    Write an alert hash to the SolGuard Registry on Solana.

    Returns the transaction signature if successful, None otherwise.

    Note: This is a stub that shows the intended flow.
    Full implementation requires:
    1. anchor deploy to get the real program ID
    2. A funded keypair for the authority wallet
    3. Transaction construction using anchorpy or solders
    """
    keypair_path = os.getenv("SOLANA_KEYPAIR_PATH", "")
    if not keypair_path or REGISTRY_PROGRAM_ID.startswith("SGRD"):
        # Program not deployed yet — skip on-chain write
        return None

    try:
        # Load keypair
        with open(os.path.expanduser(keypair_path)) as f:
            secret = json.load(f)
        authority = Keypair.from_bytes(bytes(secret))

        # Compute alert hash
        alert_hash = compute_alert_hash(alert)

        # Derive PDAs
        registry_pda, _ = derive_registry_pda()
        alert_pda, _ = derive_alert_pda(alert_index)

        # TODO: Build and send the transaction using anchorpy
        # This will be wired up after `anchor deploy`
        #
        # tx = await program.rpc.record_alert(
        #     Pubkey.from_string(alert["program_id"]),
        #     RISK_LEVEL_MAP.get(alert["risk_level"], 1),
        #     EVENT_TYPE_MAP.get(alert["event_type"], 0),
        #     list(alert_hash),
        #     Pubkey.from_string(alert.get("old_authority", SYSTEM_PROGRAM_ID)),
        #     Pubkey.from_string(alert.get("new_authority", SYSTEM_PROGRAM_ID)),
        #     ctx=Context(
        #         accounts={
        #             "registry": registry_pda,
        #             "alert": alert_pda,
        #             "authority": authority.pubkey(),
        #             "system_program": SYSTEM_PROGRAM_ID,
        #         },
        #         signers=[authority],
        #     ),
        # )
        # return str(tx)

        print(f"  📝 On-chain write ready for alert #{alert_index} (program not yet deployed)")
        return None

    except Exception as e:
        print(f"  ⚠️  On-chain write failed: {e}")
        return None
