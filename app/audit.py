from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional, Dict

import psycopg2
from psycopg2.extras import Json

import os

# External audit DB connection
_AUDIT_DB_CONFIG = {
    "host": os.getenv("AUDIT_DB_HOST", ""),
    "port": int(os.getenv("AUDIT_DB_PORT", "5432")),
    "user": os.getenv("AUDIT_DB_USER", "postgres"),
    "password": os.getenv("AUDIT_DB_PASSWORD", ""),  # Must be set in .env
    "dbname": os.getenv("AUDIT_DB_NAME", "postgres"),
    "sslmode": "require",
    "connect_timeout": 5,
}


def _get_conn():
    return psycopg2.connect(**_AUDIT_DB_CONFIG)


def _ensure_table() -> None:
    """Create the audit table if it does not exist and ensure new columns exist.

    Table: change_log
    Columns:
      id BIGSERIAL PK
      event_time TIMESTAMPTZ default now()
      user_id INTEGER
      action TEXT
      entity TEXT  -- 'portfolio' | 'option_leg'
      entity_id INTEGER
      portfolio_id INTEGER NULL
      details JSONB NULL
    """
    try:
        conn = _get_conn()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS change_log (
                  id BIGSERIAL PRIMARY KEY,
                  event_time TIMESTAMPTZ DEFAULT NOW(),
                  user_id INTEGER,
                  username TEXT NULL,
                  action TEXT,
                  entity TEXT,
                  entity_id INTEGER,
                  portfolio_id INTEGER NULL,
                  details JSONB NULL,
                  portfolio_snapshot JSONB NULL
                );
                """
            )
            # Backward-compatible alters if table already existed
            cur.execute("ALTER TABLE change_log ADD COLUMN IF NOT EXISTS username TEXT NULL;")
            cur.execute("ALTER TABLE change_log ADD COLUMN IF NOT EXISTS portfolio_snapshot JSONB NULL;")
        conn.close()
    except Exception as exc:
        # Fail silently; never block main flow due to audit DB issues
        print(f"[AUDIT] Failed to ensure table: {exc}")


def log_change(
    *,
    action: str,
    entity: str,
    entity_id: Optional[int],
    user_id: Optional[int],
    username: Optional[str] = None,
    portfolio_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    portfolio_snapshot: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert a single audit log entry. Never raises.

    This function intentionally opens and closes a new connection per call
    to keep the implementation simple and robust for occasional writes.
    """
    try:
        conn = _get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO change_log (user_id, username, action, entity, entity_id, portfolio_id, details, portfolio_snapshot)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        username,
                        action,
                        entity,
                        entity_id,
                        portfolio_id,
                        Json(details, dumps=lambda d: json.dumps(d, default=str)) if details is not None else None,
                        Json(portfolio_snapshot, dumps=lambda d: json.dumps(d, default=str)) if portfolio_snapshot is not None else None,
                    ),
                )
        conn.close()
    except Exception as exc:
        # Never block; print and continue
        print(f"[AUDIT] Failed to write audit log: {exc}")


def get_stats() -> Dict[str, Any]:
    """Return basic stats from audit DB (row count). Never raises."""
    stats = {"ok": False, "row_count": 0}
    try:
        conn = _get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM change_log")
                stats["row_count"] = cur.fetchone()[0]
        conn.close()
        stats["ok"] = True
    except Exception as exc:
        print(f"[AUDIT] stats error: {exc}")
    return stats


def fetch_recent(limit: int = 50) -> list[dict]:
    """Fetch recent audit rows. Never raises; returns [] on failure."""
    rows: list[dict] = []
    try:
        conn = _get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_time, user_id, action, entity, entity_id, portfolio_id, details
                    FROM change_log
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                for r in cur.fetchall():
                    rows.append(
                        {
                            "id": r[0],
                            "event_time": r[1].isoformat() if r[1] else None,
                            "user_id": r[2],
                            "action": r[3],
                            "entity": r[4],
                            "entity_id": r[5],
                            "portfolio_id": r[6],
                            "details": r[7],
                        }
                    )
        conn.close()
    except Exception as exc:
        print(f"[AUDIT] fetch_recent error: {exc}")
    return rows


# Ensure table on import
_ensure_table()


