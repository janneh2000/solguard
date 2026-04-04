"""
SolGuard — Claude AI Risk Analysis Engine
Autonomous threat assessment for Solana program upgrade events.
"""

import os
import json
import time
import anthropic
from dotenv import load_dotenv
from .metrics import claude_latency

load_dotenv()

SYSTEM_PROMPT = """You are SolGuard's autonomous security analyst for the Solana blockchain.

Your job: analyze program upgrade events and assess the risk to DeFi users.

## Context
Solana programs are upgradeable by default. The "upgrade authority" is a public key that can
redeploy new bytecode to a program at any time. If an attacker gains control of the upgrade
authority, they can replace the program with malicious code — draining all funds held by the
protocol. This happened during the FTX collapse (Nov 2022) when Serum's upgrade authority was
compromised.

## Known high-risk patterns
- Authority transfer to unknown wallet → HIGH or CRITICAL
- Authority transfer during market volatility → CRITICAL
- Program upgrade within 24h of large deposit activity → HIGH
- Buffer account loaded without prior governance vote → HIGH
- Authority transferred to a wallet with no prior protocol history → CRITICAL
- Authority set to null / burned (immutable) → LOW (this is actually good)
- Authority moved to a known multisig (e.g., Squads) → LOW

## Response format
Respond ONLY with a valid JSON object. No markdown fences, no explanation outside JSON.

{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "One sentence: what happened and why it matters.",
  "details": "2-3 sentences of technical context. Reference specific on-chain patterns.",
  "recommended_action": "Concrete steps for protocol users and integrators.",
  "indicators": ["list", "of", "risk", "indicators", "detected"]
}"""


def _mock_analysis(event: dict) -> dict:
    """
    Deterministic mock response used when Claude API is unavailable.
    Provides realistic risk assessments based on event patterns.
    """
    event_type = event.get("type", "UNKNOWN")
    new_auth = event.get("new_authority", "")
    old_auth = event.get("old_authority", "")
    program_id = event.get("program_id", "unknown")

    is_suspicious = (
        "Unknown" in new_auth
        or "XXX" in new_auth
        or new_auth == ""
        or new_auth == "detected_via_polling"
    )
    is_immutable = new_auth == "IMMUTABLE" or new_auth is None

    if is_immutable:
        return {
            "risk_level": "LOW",
            "summary": f"Program {program_id[:16]}... authority burned — now immutable.",
            "details": (
                "The upgrade authority has been set to null, making the program permanently immutable. "
                "This is a positive security action that prevents any future code changes. "
                "No further monitoring is needed for upgrade events on this program."
            ),
            "recommended_action": "No action needed. Program is now immutable and cannot be upgraded.",
            "indicators": ["authority_burned", "immutable"],
            "program_id": program_id,
            "tx_signature": event.get("tx_signature", "unknown"),
            "source": "mock",
        }
    elif event_type == "SET_AUTHORITY" and is_suspicious:
        return {
            "risk_level": "CRITICAL",
            "summary": f"Upgrade authority for {program_id[:16]}... transferred to an unrecognized wallet.",
            "details": (
                "The program's upgrade authority has been moved to a wallet with no known protocol history. "
                "This mirrors the attack vector that compromised protocols during the FTX collapse in November 2022. "
                "Any protocol integrating this program should treat it as potentially compromised."
            ),
            "recommended_action": "Pause integrations immediately. Verify the new authority on-chain. Contact the protocol team via official channels.",
            "indicators": ["unknown_authority", "no_governance_record", "high_tvl_program"],
            "program_id": program_id,
            "tx_signature": event.get("tx_signature", "unknown"),
            "source": "mock",
        }
    elif event_type == "SET_AUTHORITY":
        return {
            "risk_level": "HIGH",
            "summary": f"Upgrade authority change detected on {program_id[:16]}...",
            "details": (
                "The program's upgrade authority has been transferred to a new key. "
                "This may be a routine governance action (e.g., migration to a Squads multisig) or could indicate unauthorized access. "
                "Cross-reference against the protocol's governance proposals before clearing."
            ),
            "recommended_action": "Monitor the new authority wallet. Check protocol governance channels for announcements.",
            "indicators": ["authority_change", "requires_verification"],
            "program_id": program_id,
            "tx_signature": event.get("tx_signature", "unknown"),
            "source": "mock",
        }
    elif event_type == "UPGRADE":
        return {
            "risk_level": "HIGH",
            "summary": f"Program bytecode redeployment detected on {program_id[:16]}...",
            "details": (
                "A new version of the program has been deployed to mainnet. "
                "All instruction interfaces, account validations, and business logic may have changed. "
                "Downstream integrators should re-audit before continuing operations."
            ),
            "recommended_action": "Freeze new deposits until the upgrade is reviewed. Pull the new IDL and diff against the previous version.",
            "indicators": ["bytecode_change", "requires_audit"],
            "program_id": program_id,
            "tx_signature": event.get("tx_signature", "unknown"),
            "source": "mock",
        }
    else:
        return {
            "risk_level": "MEDIUM",
            "summary": f"Upgrade-related event ({event_type}) detected on {program_id[:16]}...",
            "details": "A buffer account or initialization event was detected that may precede a program upgrade.",
            "recommended_action": "Monitor for a follow-up UPGRADE event. No immediate action required.",
            "indicators": ["buffer_activity", "pre_upgrade_signal"],
            "program_id": program_id,
            "tx_signature": event.get("tx_signature", "unknown"),
            "source": "mock",
        }


async def analyze_event(event: dict) -> dict:
    """
    Calls Claude to analyze a Solana program upgrade event.
    Falls back to mock analysis if the API is unavailable.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key or api_key == "your_key_here":
        print("  ⚠️  No API key — using mock analysis")
        return _mock_analysis(event)

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
Transaction: {event.get('tx_signature', 'unknown')}
Slot: {event.get('slot', 0)}

Return JSON only."""
            }],
        )

        elapsed = time.time() - start
        claude_latency.observe(elapsed)

        text = message.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["program_id"] = event.get("program_id", "unknown")
        result["tx_signature"] = event.get("tx_signature", "unknown")
        result["source"] = "claude"
        result["latency_ms"] = round(elapsed * 1000)
        return result

    except anthropic.AuthenticationError:
        print("  ⚠️  API key invalid — using mock analysis")
        return _mock_analysis(event)

    except Exception as e:
        print(f"  ⚠️  Claude API error ({type(e).__name__}: {str(e)[:60]}) — using mock analysis")
        return _mock_analysis(event)
