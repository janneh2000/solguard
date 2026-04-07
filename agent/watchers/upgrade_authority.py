# agent/watchers/upgrade_authority.py
"""
SolGuard — Upgrade Authority Watcher
Monitors program upgrade authorities on Solana mainnet.
Includes Squads multisig detection for risk assessment.
"""

import asyncio
import os
import struct
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

UPGRADEABLE_LOADER = "BPFLoaderUpgradeab1e11111111111111111111111"

# Squads v3 and v4 program IDs — used to detect multisig authorities
SQUADS_PROGRAM_IDS = {
    "SMPLecH534NA9acpos4G6x7uf3LWbCAwZQE9e8ZekMu",   # Squads v3
    "SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf",   # Squads v4
}

# ── Expanded Watchlist ────────────────────────────────────────────────────────
# 15 major Solana DeFi protocols monitored by default
WATCHED_PROGRAMS = {
    # DEX / AMM
    "Jupiter v6":          "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    "Jupiter Perps":       "PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu",
    "Raydium AMM":         "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "Raydium CLMM":        "CAMMCzo5YL8w4VFF8KVHr7wifgk7jfhELM25LNNrsEgc",
    "Orca Whirlpool":      "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "Meteora DLMM":        "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
    # Lending
    "Kamino Lending":      "KLend2g3cP87fffoy8q1mQqGKjrL1AMLkohkowi9oec",
    "Marginfi":            "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA",
    # Perps / Trading
    "Drift Protocol":      "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",
    # Liquid Staking
    "Marinade Finance":    "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD",
    "Sanctum (Infinity)":  "5ocnV1qiCgaQR8Jb8xWnVbApfaygJ8tNoZfgPwsgx9kx",
    # Token Launchpads
    "PumpFun":             "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    # Infrastructure
    "Pyth Oracle":         "FsJ3A3u2vn5cTVofAjvy6y5kwABJAqYWpe4975bi2epH",
    "Wormhole":            "worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth",
    # Governance
    "Squads v4":           "SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf",
}


def get_program_data_address(program_id: Pubkey) -> Pubkey:
    """Derives the ProgramData PDA for a given program."""
    seeds = [bytes(program_id)]
    program_data, _ = Pubkey.find_program_address(
        seeds,
        Pubkey.from_string(UPGRADEABLE_LOADER)
    )
    return program_data


async def get_upgrade_authority(client: AsyncClient, program_id: str) -> str | None:
    """
    Returns the current upgrade authority for a program.
    Returns 'IMMUTABLE' if the authority has been burned.
    Returns None if the account doesn't exist.
    """
    program_key = Pubkey.from_string(program_id)
    program_data_key = get_program_data_address(program_key)

    account = await client.get_account_info(program_data_key, encoding="base64")
    if not account.value:
        return None

    # ProgramData account layout:
    # [0..4]   discriminator (4 bytes)
    # [4..12]  last_modified_slot (u64, 8 bytes)
    # [12]     upgrade_authority option flag (1 = Some, 0 = None/immutable)
    # [13..45] upgrade_authority pubkey (32 bytes, only if flag == 1)
    data = bytes(account.value.data)

    if len(data) < 45:
        return None

    if data[12] == 0:
        return "IMMUTABLE"

    authority_bytes = data[13:45]
    return str(Pubkey.from_bytes(authority_bytes))


async def is_squads_multisig(client: AsyncClient, address: str) -> bool:
    """
    Check if an address is a Squads multisig account.
    Squads PDAs are owned by the Squads program.
    """
    if not address or address == "IMMUTABLE":
        return False

    try:
        pubkey = Pubkey.from_string(address)
        account = await client.get_account_info(pubkey)
        if account.value:
            owner = str(account.value.owner)
            return owner in SQUADS_PROGRAM_IDS
    except Exception:
        pass
    return False


async def check_authority_is_multisig(client: AsyncClient, authority: str) -> dict:
    """
    Returns enrichment data about an authority address.
    Used by the risk engine to adjust risk levels.
    """
    if not authority or authority == "IMMUTABLE":
        return {"is_multisig": False, "is_immutable": authority == "IMMUTABLE"}

    is_multisig = await is_squads_multisig(client, authority)
    return {
        "is_multisig": is_multisig,
        "is_immutable": False,
        "multisig_program": "Squads" if is_multisig else None,
    }


# ── Quick test — run directly: python3 -m agent.watchers.upgrade_authority ───
async def _test():
    rpc = os.getenv("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
    client = AsyncClient(rpc)
    print(f"\n🔭 SolGuard — reading upgrade authorities from mainnet\n{'─'*60}")
    for name, pid in WATCHED_PROGRAMS.items():
        try:
            authority = await get_upgrade_authority(client, pid)
            status = "🔴 IMMUTABLE" if authority == "IMMUTABLE" else f"🔑 {authority[:20]}..." if authority else "❓ not found"
            print(f"  {name:<20} {status}")
        except Exception as e:
            print(f"  {name:<20} ⚠️  error: {e}")
    await client.close()
    print(f"{'─'*60}\n✅ Done\n")

if __name__ == "__main__":
    asyncio.run(_test())