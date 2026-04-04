"""
SolGuard — SQLite database for persistent alert history
Lightweight, zero-config, perfect for hackathon demos and local deployments.
"""

import sqlite3
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AlertRecord:
    id: str
    timestamp: str
    program_id: str
    program_name: str
    event_type: str
    risk_level: str
    summary: str
    details: str
    recommended_action: str
    old_authority: str
    new_authority: str
    tx_signature: str
    source: str  # "claude" or "mock"


class Database:
    def __init__(self, path: str = "solguard_alerts.db"):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None

    def init(self):
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                program_id TEXT NOT NULL,
                program_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                summary TEXT,
                details TEXT,
                recommended_action TEXT,
                old_authority TEXT,
                new_authority TEXT,
                tx_signature TEXT,
                source TEXT
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp DESC)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_risk ON alerts(risk_level)
        """)
        self._conn.commit()

    def save_alert(self, alert: AlertRecord):
        self._conn.execute(
            """INSERT OR REPLACE INTO alerts
               (id, timestamp, program_id, program_name, event_type, risk_level,
                summary, details, recommended_action, old_authority, new_authority,
                tx_signature, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.id, alert.timestamp, alert.program_id, alert.program_name,
                alert.event_type, alert.risk_level, alert.summary, alert.details,
                alert.recommended_action, alert.old_authority, alert.new_authority,
                alert.tx_signature, alert.source,
            ),
        )
        self._conn.commit()

    def get_alerts(self, limit: int = 50, risk_level: str | None = None) -> list[AlertRecord]:
        query = "SELECT * FROM alerts"
        params = []
        if risk_level:
            query += " WHERE risk_level = ?"
            params.append(risk_level)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [AlertRecord(**dict(zip(columns, row))) for row in rows]

    def get_stats(self) -> dict:
        cursor = self._conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN risk_level = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END) as low
            FROM alerts
        """)
        row = cursor.fetchone()
        return {
            "total": row[0] or 0,
            "critical": row[1] or 0,
            "high": row[2] or 0,
            "medium": row[3] or 0,
            "low": row[4] or 0,
        }
