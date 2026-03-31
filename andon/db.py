"""SQLite persistence layer for the Andon system."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from .models import (
    AndonSignal,
    EscalationEvent,
    EscalationLevel,
    Product,
    SignalCategory,
    SignalSeverity,
    SignalStatus,
    Stage,
    StageName,
    StageStatus,
)

DEFAULT_DB_PATH = Path.home() / ".andon" / "andon.db"


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(val) if val else None


@contextmanager
def _conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    owner         TEXT NOT NULL,
    business_unit TEXT,
    current_stage TEXT NOT NULL DEFAULT 'ideation',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stages (
    id         TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'not_started',
    owner      TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    id                TEXT PRIMARY KEY,
    product_id        TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    stage_name        TEXT NOT NULL,
    severity          TEXT NOT NULL,
    category          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'open',
    title             TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    raised_by         TEXT NOT NULL,
    raised_at         TEXT NOT NULL,
    acknowledged_by   TEXT,
    acknowledged_at   TEXT,
    resolved_by       TEXT,
    resolved_at       TEXT,
    root_cause        TEXT,
    corrective_action TEXT,
    escalation_level  INTEGER NOT NULL DEFAULT 0,
    tags              TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS escalation_events (
    id           TEXT PRIMARY KEY,
    signal_id    TEXT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    from_level   INTEGER NOT NULL,
    to_level     INTEGER NOT NULL,
    escalated_by TEXT NOT NULL,
    reason       TEXT NOT NULL,
    escalated_at TEXT NOT NULL
);
"""


class AndonDB:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        with _conn(self.db_path) as con:
            con.executescript(SCHEMA)

    # ── Products ──────────────────────────────────────────────────────────────

    def save_product(self, product: Product) -> None:
        with _conn(self.db_path) as con:
            # Use upsert (not INSERT OR REPLACE) to avoid cascade-deleting child rows.
            con.execute(
                """INSERT INTO products
                   (id, name, owner, business_unit, current_stage, created_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name,
                     owner=excluded.owner,
                     business_unit=excluded.business_unit,
                     current_stage=excluded.current_stage""",
                (
                    product.id,
                    product.name,
                    product.owner,
                    product.business_unit,
                    product.current_stage.value,
                    product.created_at.isoformat(),
                ),
            )

    def get_product(self, product_id: str) -> Optional[Product]:
        with _conn(self.db_path) as con:
            row = con.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if not row:
                return None
            return self._hydrate_product(con, row)

    def list_products(self) -> list[Product]:
        with _conn(self.db_path) as con:
            rows = con.execute(
                "SELECT * FROM products ORDER BY created_at DESC"
            ).fetchall()
            return [self._hydrate_product(con, r) for r in rows]

    def delete_product(self, product_id: str) -> bool:
        with _conn(self.db_path) as con:
            cur = con.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return cur.rowcount > 0

    def _hydrate_product(self, con: sqlite3.Connection, row: sqlite3.Row) -> Product:
        stage_rows = con.execute(
            "SELECT * FROM stages WHERE product_id = ? ORDER BY rowid", (row["id"],)
        ).fetchall()
        stages = [
            Stage(
                id=sr["id"],
                product_id=sr["product_id"],
                name=StageName(sr["name"]),
                status=StageStatus(sr["status"]),
                owner=sr["owner"],
                created_at=datetime.fromisoformat(sr["created_at"]),
            )
            for sr in stage_rows
        ]
        signal_rows = con.execute(
            "SELECT * FROM signals WHERE product_id = ? ORDER BY raised_at DESC",
            (row["id"],),
        ).fetchall()
        signals = [self._hydrate_signal(con, sr) for sr in signal_rows]
        return Product(
            id=row["id"],
            name=row["name"],
            owner=row["owner"],
            business_unit=row["business_unit"],
            current_stage=StageName(row["current_stage"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            stages=stages,
            signals=signals,
        )

    # ── Stages ────────────────────────────────────────────────────────────────

    def save_stage(self, stage: Stage) -> None:
        with _conn(self.db_path) as con:
            con.execute(
                """INSERT INTO stages
                   (id, product_id, name, status, owner, created_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     status=excluded.status,
                     owner=excluded.owner""",
                (
                    stage.id,
                    stage.product_id,
                    stage.name.value,
                    stage.status.value,
                    stage.owner,
                    stage.created_at.isoformat(),
                ),
            )

    def get_stage(self, stage_id: str) -> Optional[Stage]:
        with _conn(self.db_path) as con:
            row = con.execute(
                "SELECT * FROM stages WHERE id = ?", (stage_id,)
            ).fetchone()
            if not row:
                return None
            return Stage(
                id=row["id"],
                product_id=row["product_id"],
                name=StageName(row["name"]),
                status=StageStatus(row["status"]),
                owner=row["owner"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    # ── Signals ───────────────────────────────────────────────────────────────

    def save_signal(self, signal: AndonSignal) -> None:
        with _conn(self.db_path) as con:
            # Use upsert to avoid cascade-deleting escalation_events child rows.
            con.execute(
                """INSERT INTO signals
                   (id, product_id, stage_name, severity, category, status,
                    title, description, raised_by, raised_at,
                    acknowledged_by, acknowledged_at, resolved_by, resolved_at,
                    root_cause, corrective_action, escalation_level, tags)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     severity=excluded.severity,
                     category=excluded.category,
                     status=excluded.status,
                     acknowledged_by=excluded.acknowledged_by,
                     acknowledged_at=excluded.acknowledged_at,
                     resolved_by=excluded.resolved_by,
                     resolved_at=excluded.resolved_at,
                     root_cause=excluded.root_cause,
                     corrective_action=excluded.corrective_action,
                     escalation_level=excluded.escalation_level,
                     tags=excluded.tags""",
                (
                    signal.id,
                    signal.product_id,
                    signal.stage_name.value,
                    signal.severity.value,
                    signal.category.value,
                    signal.status.value,
                    signal.title,
                    signal.description,
                    signal.raised_by,
                    signal.raised_at.isoformat(),
                    signal.acknowledged_by,
                    signal.acknowledged_at.isoformat() if signal.acknowledged_at else None,
                    signal.resolved_by,
                    signal.resolved_at.isoformat() if signal.resolved_at else None,
                    signal.root_cause,
                    signal.corrective_action,
                    signal.escalation_level.value,
                    json.dumps(signal.tags),
                ),
            )

    def get_signal(self, signal_id: str) -> Optional[AndonSignal]:
        with _conn(self.db_path) as con:
            row = con.execute(
                "SELECT * FROM signals WHERE id = ?", (signal_id,)
            ).fetchone()
            if not row:
                return None
            return self._hydrate_signal(con, row)

    def list_signals(
        self,
        product_id: Optional[str] = None,
        status: Optional[SignalStatus] = None,
        severity: Optional[SignalSeverity] = None,
    ) -> list[AndonSignal]:
        clauses: list[str] = []
        params: list = []
        if product_id:
            clauses.append("product_id = ?")
            params.append(product_id)
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        if severity:
            clauses.append("severity = ?")
            params.append(severity.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with _conn(self.db_path) as con:
            rows = con.execute(
                f"SELECT * FROM signals {where} ORDER BY raised_at DESC", params
            ).fetchall()
            return [self._hydrate_signal(con, r) for r in rows]

    def _hydrate_signal(self, con: sqlite3.Connection, row: sqlite3.Row) -> AndonSignal:
        esc_rows = con.execute(
            "SELECT * FROM escalation_events WHERE signal_id = ? ORDER BY escalated_at",
            (row["id"],),
        ).fetchall()
        history = [
            EscalationEvent(
                id=er["id"],
                signal_id=er["signal_id"],
                from_level=EscalationLevel(er["from_level"]),
                to_level=EscalationLevel(er["to_level"]),
                escalated_by=er["escalated_by"],
                reason=er["reason"],
                escalated_at=datetime.fromisoformat(er["escalated_at"]),
            )
            for er in esc_rows
        ]
        return AndonSignal(
            id=row["id"],
            product_id=row["product_id"],
            stage_name=StageName(row["stage_name"]),
            severity=SignalSeverity(row["severity"]),
            category=SignalCategory(row["category"]),
            status=SignalStatus(row["status"]),
            title=row["title"],
            description=row["description"],
            raised_by=row["raised_by"],
            raised_at=datetime.fromisoformat(row["raised_at"]),
            acknowledged_by=row["acknowledged_by"],
            acknowledged_at=_parse_dt(row["acknowledged_at"]),
            resolved_by=row["resolved_by"],
            resolved_at=_parse_dt(row["resolved_at"]),
            root_cause=row["root_cause"],
            corrective_action=row["corrective_action"],
            escalation_level=EscalationLevel(row["escalation_level"]),
            escalation_history=history,
            tags=json.loads(row["tags"]),
        )

    # ── Escalation events ─────────────────────────────────────────────────────

    def save_escalation(self, event: EscalationEvent) -> None:
        with _conn(self.db_path) as con:
            con.execute(
                """INSERT OR REPLACE INTO escalation_events
                   (id, signal_id, from_level, to_level, escalated_by, reason, escalated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    event.id,
                    event.signal_id,
                    event.from_level.value,
                    event.to_level.value,
                    event.escalated_by,
                    event.reason,
                    event.escalated_at.isoformat(),
                ),
            )
