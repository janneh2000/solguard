"""
SolGuard — Claude AI Risk Analysis Engine
Autonomous threat assessment for Solana program upgrade events.

v2 additions:
  - Jito bundle heuristic (atomic MEV-bundled upgrades)
  - Multisig threshold-reduction detector
  - Replay-mode flag produces pre-crafted step narration
  - Hard output schema validation (defense against prompt injection)
"""

import os
import json
import time
import anthropic
from dotenv import load_dotenv
from .metrics import claude_latency

load_dotenv()

VALID_RISK = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_PATTERNS = {"none", "serum_ftx", "drift_dprk", "jito_bundle_upgrade",
                  "multisig_threshold_reduction", "generic_authority_hijack"}

SYSTEM_PROMPT = """You are SolGuard's autonomous security analyst for the Solana blockchain.

Your job: analyze program upgrade events and assess the risk to DeFi users and integrators.

## Context
Solana programs are upgradeable by default via BPFLoaderUpgradeable. The "upgrade authority" is a
public key that can redeploy new bytecode at any time. If an attacker gains control of the upgrade
authority, they can replace the program with malicious code — draining all funds held by the protocol.

## CRITICAL: Recent Real-World Attack Patterns

### The Drift Protocol Hack (April 1, 2026) — $285M stolen
- DPRK state-sponsored hackers (UNC4736) executed a 6-month social engineering campaign
- Attackers posed as a quant trading firm, built trust at crypto conferences over months
- Compromised 2 of 5 multisig signers through malicious code repos and TestFlight apps
- Used DURABLE NONCE TRANSACTIONS to pre-sign admin transfers days before execution
- Migrated Security Council to a new 2/5 multisig with ZERO TIMELOCK
- Created a fake token (CarbonVote) and manipulated oracles to use as collateral
- Drained $285M in 10 seconds once pre-signed transactions were triggered
- KEY LESSON: The vulnerability was NOT in smart contracts — it was in governance and human trust

### The Serum/FTX Incident (November 2022)
- Serum's upgrade authority was compromised during the FTX collapse
- Community had to emergency-fork the program to prevent exploitation
- No automated detection system existed at the time

### Jito Bundle Upgrades (Emerging pattern)
- Attackers can bundle buffer init + write + upgrade instructions in a single
  Jito block-atomic bundle, making the upgrade indivisible and impossible to
  front-run or pause mid-way. A bundled upgrade on a high-TVL program with no
  public proposal should be treated as suspicious.

## Known risk patterns (use these for scoring)

### CRITICAL indicators
- Authority transferred to an unknown wallet with no prior on-chain history
- Authority transferred during high market volatility or a known exploit in progress
- Authority change + large fund movements in the same slot range
- New authority is an EOA (externally owned account) rather than a multisig/PDA
- Security Council or admin multisig migration with zero timelock (Drift attack pattern)
- Durable nonce accounts created targeting program authorities (pre-signed attack staging)
- Multiple authority changes on the same program in a short time window
- Authority change immediately after a multisig threshold reduction
- Jito-bundled buffer+upgrade instructions on a high-TVL program

### HIGH indicators
- Program bytecode upgrade (UPGRADE event) without a matching governance proposal
- Authority transferred to a new key without public announcement
- Buffer account initialized (INITIALIZE_BUFFER) on a high-TVL program
- Authority change on a program that was previously immutable
- Multisig threshold reduced (e.g., 4/7 → 2/5) without governance vote
- New durable nonce accounts created by addresses interacting with watched programs

### MEDIUM indicators
- Buffer account activity that may precede an upgrade
- Authority transferred between known team wallets (routine rotation)
- Scheduled maintenance upgrade with governance approval
- Multisig signer rotation with proper timelock

### LOW indicators (positive events)
- Authority burned (set to null) — program becomes immutable. This is POSITIVE.
- Authority moved to a Squads multisig (addresses owned by SMPLecH534NA9acpos4G6x7uf3LWbCAwZQE9e8ZekMu
  or SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf). This is a SECURITY UPGRADE.
- Routine governance-approved upgrade with matching Realms/Squads proposal
- Timelock increase on admin operations

## Response format
Respond ONLY with a valid JSON object. No markdown fences, no explanation outside JSON.

{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "One sentence: what happened and why it matters.",
  "details": "2-3 sentences of technical context. Reference specific real-world attack patterns when relevant.",
  "recommended_action": "Concrete steps for protocol users and integrators.",
  "indicators": ["list", "of", "risk", "indicators", "detected"],
  "attack_pattern_match": "none|serum_ftx|drift_dprk|jito_bundle_upgrade|multisig_threshold_reduction|generic_authority_hijack"
}"""


def _validate_result(raw: dict, event: dict) -> dict:
    """Coerce the model's response into a known-safe shape."""
    risk = str(raw.get("risk_level", "")).upper()
    if risk not in VALID_RISK:
        risk = "MEDIUM"
    pattern = str(raw.get("attack_pattern_match", "none"))
    if pattern not in VALID_PATTERNS:
        pattern = "none"
    indicators = raw.get("indicators", [])
    if not isinstance(indicators, list):
        indicators = []
    return {
        "risk_level": risk,
        "summary": str(raw.get("summary", ""))[:500],
        "details": str(raw.get("details", ""))[:1500],
        "recommended_action": str(raw.get("recommended_action", ""))[:500],
        "indicators": [str(i)[:80] for i in indicators[:20]],
        "attack_pattern_match": pattern,
        "program_id": event.get("program_id", "unknown"),
        "tx_signature": event.get("tx_signature", "unknown"),
    }


def _mock_analysis(event: dict) -> dict:
    """
    Deterministic mock response used when Claude API is unavailable.
    Covers every event type the agent emits — including the Drift replay flow.
    """
    event_type = event.get("type", "UNKNOWN")
    new_auth = event.get("new_authority", "") or ""
    program_id = event.get("program_id", "unknown")
    is_multisig = event.get("new_authority_is_multisig", False)
    is_replay = event.get("replay", False)

    is_suspicious = (
        "Unknown" in new_auth
        or "XXX" in new_auth
        or new_auth == ""
        or new_auth == "detected_via_polling"
    ) and event_type == "SET_AUTHORITY"
    is_immutable = new_auth == "IMMUTABLE" or new_auth is None

    base = {
        "program_id": program_id,
        "tx_signature": event.get("tx_signature", "unknown"),
        "source": "mock",
    }

    # ── Drift replay staging ────────────────────────────────────────────────
    if is_replay and event_type == "DURABLE_NONCE_ACTIVITY":
        return {**base, "risk_level": "HIGH",
                "summary": "STAGE 1/3 — Durable nonce account created near Drift Protocol authority.",
                "details": "This mirrors the opening move of the April 2026 Drift hack: attackers create durable nonce accounts so that 'routine' pre-signed transactions can be triggered days later. No funds have moved yet, but the attack is being staged.",
                "recommended_action": "Freeze any pending multisig approvals. Audit recent signer activity. Cross-check against official Drift governance.",
                "indicators": ["durable_nonce_created", "staging_phase", "drift_pattern_1_of_3"],
                "attack_pattern_match": "drift_dprk"}

    if is_replay and event_type == "MULTISIG_THRESHOLD_CHANGE":
        return {**base, "risk_level": "CRITICAL",
                "summary": "STAGE 2/3 — Security Council multisig migrated to 2/5 with ZERO TIMELOCK.",
                "details": "The multisig threshold was reduced and the timelock was removed — the exact configuration used on April 1, 2026, just before $285M was drained from Drift. Removing the timelock means the pre-signed transfer from Stage 1 can now execute instantly.",
                "recommended_action": "EMERGENCY: Notify SEAL 911. Revoke pending signatures. Freeze protocol interactions. Verify signer devices have not been compromised.",
                "indicators": ["timelock_removed", "threshold_reduced", "drift_pattern_2_of_3"],
                "attack_pattern_match": "multisig_threshold_reduction"}

    if is_replay and event_type == "SET_AUTHORITY":
        return {**base, "risk_level": "CRITICAL",
                "summary": "STAGE 3/3 — Admin authority transferred to an unverified wallet. Attack complete.",
                "details": "The pre-signed admin transfer from Stage 1 has been triggered. Authority is now held by a wallet with no prior on-chain history. In the original Drift attack this step was followed within 10 seconds by $285M being drained.",
                "recommended_action": "Protocol is presumed compromised. Halt all integrations. Pull all collateral. Contact SEAL 911 and the Solana Foundation security team.",
                "indicators": ["authority_hijacked", "post_attack", "drift_pattern_3_of_3"],
                "attack_pattern_match": "drift_dprk"}

    # ── Normal dispatch ─────────────────────────────────────────────────────
    if is_immutable:
        return {**base, "risk_level": "LOW",
                "summary": f"Program {program_id[:16]}... authority burned — now immutable.",
                "details": "The upgrade authority has been set to null, making the program permanently immutable. This is a positive security action that prevents any future code changes. No further monitoring is needed for upgrade events on this program.",
                "recommended_action": "No action needed. Program is now immutable and cannot be upgraded.",
                "indicators": ["authority_burned", "immutable"],
                "attack_pattern_match": "none"}

    if event_type == "SET_AUTHORITY" and is_multisig:
        return {**base, "risk_level": "LOW",
                "summary": f"Program {program_id[:16]}... authority migrated to a Squads multisig — security upgrade.",
                "details": "The upgrade authority has been transferred to a Squads multisig wallet. This is a positive security action: program upgrades now require multiple signers, reducing single-point-of-failure risk. Recommended by Solana security best practices.",
                "recommended_action": "No immediate action needed. Verify the multisig configuration matches the protocol's governance structure.",
                "indicators": ["squads_multisig", "security_upgrade", "multi_signature"],
                "attack_pattern_match": "none"}

    if event_type == "SET_AUTHORITY" and is_suspicious:
        return {**base, "risk_level": "CRITICAL",
                "summary": f"Upgrade authority for {program_id[:16]}... transferred to an unrecognized wallet.",
                "details": "The program's upgrade authority has been moved to a wallet with no known protocol history. This mirrors the attack vector that compromised protocols during the FTX collapse and the pattern seen in the Drift DPRK hack.",
                "recommended_action": "Pause integrations immediately. Verify the new authority on-chain. Contact the protocol team via official channels.",
                "indicators": ["unknown_authority", "no_governance_record", "high_tvl_program"],
                "attack_pattern_match": "generic_authority_hijack"}

    if event_type == "SET_AUTHORITY":
        return {**base, "risk_level": "HIGH",
                "summary": f"Upgrade authority change detected on {program_id[:16]}...",
                "details": "The program's upgrade authority has been transferred to a new key. This may be routine governance (e.g., migration to a Squads multisig) or could indicate unauthorized access. Cross-reference against the protocol's governance proposals.",
                "recommended_action": "Monitor the new authority wallet. Check protocol governance channels for announcements.",
                "indicators": ["authority_change", "requires_verification"],
                "attack_pattern_match": "none"}

    if event_type == "UPGRADE":
        return {**base, "risk_level": "HIGH",
                "summary": f"Program bytecode redeployment detected on {program_id[:16]}...",
                "details": "A new version of the program has been deployed to mainnet. Instruction interfaces, account validations, and business logic may have changed. Downstream integrators should re-audit.",
                "recommended_action": "Freeze new deposits until the upgrade is reviewed. Pull the new IDL and diff against the previous version.",
                "indicators": ["bytecode_change", "requires_audit"],
                "attack_pattern_match": "none"}

    if event_type == "DURABLE_NONCE_ACTIVITY":
        return {**base, "risk_level": "HIGH",
                "summary": f"Durable nonce activity detected near {program_id[:16]}... authority — Drift attack pattern.",
                "details": "New durable nonce accounts were observed around a watched protocol's authority. This is the pre-staging technique used in the April 2026 Drift hack — attackers get multisig signers to pre-sign 'routine' transactions, then trigger them later.",
                "recommended_action": "Alert the protocol team. Audit recent multisig signing requests. Verify no pre-signed transactions are pending.",
                "indicators": ["durable_nonce", "pre_staging", "drift_pattern"],
                "attack_pattern_match": "drift_dprk"}

    return {**base, "risk_level": "MEDIUM",
            "summary": f"Upgrade-related event ({event_type}) detected on {program_id[:16]}...",
            "details": "A buffer account or initialization event was detected that may precede a program upgrade.",
            "recommended_action": "Monitor for a follow-up UPGRADE event. No immediate action required.",
            "indicators": ["buffer_activity", "pre_upgrade_signal"],
            "attack_pattern_match": "none"}


async def analyze_event(event: dict) -> dict:
    """
    Calls Claude to analyze a Solana program upgrade event.
    Falls back to mock analysis if the API is unavailable.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    # During replay, always use deterministic mock for consistent video narration.
    if event.get("replay"):
        return _mock_analysis(event)

    if not api_key or api_key.startswith("your_"):
        print("  ⚠️  No API key — using mock analysis")
        return _mock_analysis(event)

    is_multisig = event.get("new_authority_is_multisig", False)
    multisig_info = "Yes — Squads multisig detected (security upgrade)" if is_multisig else "No / Unknown"

    start = time.time()
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"""Analyze this Solana program upgrade event:

Program ID: {event.get('program_id', 'unknown')}
Event type: {event.get('type', 'unknown')}
Old authority: {event.get('old_authority', 'N/A')}
New authority: {event.get('new_authority', 'N/A')}
New authority is multisig: {multisig_info}
Transaction: {event.get('tx_signature', 'unknown')}
Slot: {event.get('slot', 0)}

Return JSON only."""
            }],
        )

        elapsed = time.time() - start
        claude_latency.observe(elapsed)

        text = message.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        raw = json.loads(text)
        result = _validate_result(raw, event)
        result["source"] = "claude"
        result["latency_ms"] = round(elapsed * 1000)
        return result

    except anthropic.AuthenticationError:
        print("  ⚠️  API key invalid — using mock analysis")
        return _mock_analysis(event)
    except Exception as e:
        print(f"  ⚠️  Claude API error ({type(e).__name__}: {str(e)[:80]}) — using mock analysis")
        return _mock_analysis(event)
