"""Tests for the SQLite alert database."""
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from agent.database import Database, AlertRecord


def _mk(ts="2026-04-16T12:00:00+00:00", risk="HIGH", pid="P" * 44):
    return AlertRecord(
        id=f"id_{ts}_{risk}",
        timestamp=ts,
        program_id=pid,
        program_name="Test",
        event_type="SET_AUTHORITY",
        risk_level=risk,
        summary="s",
        details="d",
        recommended_action="a",
        old_authority="",
        new_authority="",
        tx_signature="",
        source="mock",
    )


def test_save_and_fetch():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        path = tf.name
    db = Database(path=path)
    db.init()
    db.save_alert(_mk("2026-04-16T10:00:00+00:00", "CRITICAL"))
    db.save_alert(_mk("2026-04-16T11:00:00+00:00", "HIGH"))
    alerts = db.get_alerts(limit=10)
    assert len(alerts) == 2
    assert alerts[0].risk_level == "HIGH"  # DESC order


def test_reject_bad_risk_level():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        path = tf.name
    db = Database(path=path)
    db.init()
    assert db.get_alerts(risk_level="DROP TABLE alerts;--") == []


def test_stats():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        path = tf.name
    db = Database(path=path)
    db.init()
    db.save_alert(_mk("2026-04-16T10:00:00+00:00", "CRITICAL"))
    db.save_alert(_mk("2026-04-16T11:00:00+00:00", "HIGH"))
    db.save_alert(_mk("2026-04-16T12:00:00+00:00", "LOW"))
    s = db.get_stats()
    assert s["total"] == 3
    assert s["critical"] == 1
    assert s["high"] == 1
    assert s["low"] == 1


def test_timeline_shape():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        path = tf.name
    db = Database(path=path)
    db.init()
    now = datetime.now(timezone.utc).isoformat()
    db.save_alert(_mk(now, "CRITICAL"))
    t = db.get_timeline(hours=6)
    assert "hours" in t and "series" in t
    assert len(t["hours"]) == 6
    assert set(t["series"].keys()) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
