# agent/watchers/upgrade_authority.py
import asyncio
import os
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

UPGRADEABLE_LOADER = "BPFLoaderUpgradeab1e11111111111111111111111"

# Pre-loaded watchlist — the protocols SolGuard monitors by default
WATCHED_PROGRAMS = {
    "Jupiter v6":      "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    "Raydium AMM":     "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "Orca Whirlpool":  "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "Kamino Lending":  "KLend2g3cP87fffoy8q1mQqGKjrL1AMLkohkowi9oec",
    "Drift Protocol":  "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH",
    "Marinade Finance":"MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD",
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