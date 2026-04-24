"""
Tests for the Claude risk engine.

These tests cover the deterministic mock path (no network) so CI/self-tests
never depend on an API key.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from agent.claude_engine import _mock_analysis, _validate_result, analyze_event, VALID_RISK, VALID_PATTERNS


def test_immutable_is_low():
    r = _mock_analysis({"type": "SET_AUTHORITY", "new_authority": "IMMUTABLE", "program_id": "X" * 44})
    assert r["risk_level"] == "LOW"
    assert "immutable" in " ".join(r["indicators"]).lower()


def test_squads_multisig_is_low():
    r = _mock_analysis({"type": "SET_AUTHORITY", "new_authority": "abc", "new_authority_is_multisig": True, "program_id": "P" * 44})
    assert r["risk_level"] == "LOW"
    assert "security_upgrade" in r["indicators"]


def test_unknown_authority_is_critical():
    r = _mock_analysis({"type": "SET_AUTHORITY", "new_authority": "UnknownWa11etXXX", "program_id": "J" * 44})
    assert r["risk_level"] == "CRITICAL"
    assert r["attack_pattern_match"] == "generic_authority_hijack"


def test_upgrade_is_high():
    r = _mock_analysis({"type": "UPGRADE", "program_id": "M" * 44})
    assert r["risk_level"] == "HIGH"


def test_drift_replay_stage1():
    r = _mock_analysis({"type": "DURABLE_NONCE_ACTIVITY", "program_id": "D" * 44, "replay": True})
    assert r["risk_level"] == "HIGH"
    assert "1/3" in r["summary"]
    assert r["attack_pattern_match"] == "drift_dprk"


def test_drift_replay_stage3_critical():
    r = _mock_analysis({"type": "SET_AUTHORITY", "program_id": "D" * 44, "replay": True, "new_authority": "anything"})
    assert r["risk_level"] == "CRITICAL"
    assert "3/3" in r["summary"]


def test_validate_coerces_unknown_risk():
    raw = {"risk_level": "EXTREME", "summary": "x" * 2000, "details": "y", "recommended_action": "z", "indicators": ["a", "b", {"weird": "obj"}], "attack_pattern_match": "hax"}
    out = _validate_result(raw, {"program_id": "p", "tx_signature": "t"})
    assert out["risk_level"] == "MEDIUM"
    assert out["attack_pattern_match"] == "none"
    assert len(out["summary"]) <= 500
    assert all(isinstance(i, str) for i in out["indicators"])


def test_valid_pattern_set_includes_jito():
    assert "jito_bundle_upgrade" in VALID_PATTERNS
    assert "multisig_threshold_reduction" in VALID_PATTERNS


def test_analyze_event_replay_uses_mock_without_api():
    # Replay flag should always use mock — deterministic for demo
    result = asyncio.run(analyze_event({"type": "SET_AUTHORITY", "program_id": "P" * 44, "replay": True, "new_authority": "x"}))
    assert result["risk_level"] in VALID_RISK
    assert result["source"] == "mock"
