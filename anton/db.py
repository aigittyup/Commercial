"""SQLite persistence layer for Anton."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator, Optional

from .models import (
    GateCriterion,
    Product,
    ProductStatus,
    Stage,
    StageName,
    StageStatus,
    Task,
    TaskPriority,
    TaskStatus,
)

DEFAULT_DB_PATH = Path.home() / ".anton" / "anton.db"


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(val) if val else None


def _parse_date(val: Optional[str]) -> Optional[date]:
    return date.fromisoformat(val) if val else None


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
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    owner        TEXT NOT NULL,
    business_unit TEXT,
    target_market TEXT,
    status       TEXT NOT NULL DEFAULT 'active',
    current_stage TEXT NOT NULL DEFAULT 'ideation',
    tags         TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL,
    launched_at  TEXT
);

CREATE TABLE IF NOT EXISTS stages (
    id           TEXT PRIMARY KEY,
    product_id   TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'not_started',
    owner        TEXT,
    target_date  TEXT,
    completed_at TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id           TEXT PRIMARY KEY,
    stage_id     TEXT NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    owner        TEXT,
    priority     TEXT NOT NULL DEFAULT 'medium',
    status       TEXT NOT NULL DEFAULT 'open',
    due_date     TEXT,
    completed_at TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gate_criteria (
    id           TEXT PRIMARY KEY,
    stage_id     TEXT NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
    description  TEXT NOT NULL,
    is_met       INTEGER NOT NULL DEFAULT 0,
    verified_by  TEXT,
    verified_at  TEXT
);
"""


class AntonDB:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        with _conn(self.db_path) as con:
            con.executescript(SCHEMA)

    # ── Products ─────────────────────────────────────────────────────────────

    def save_product(self, product: Product) -> None:
        with _conn(self.db_path) as con:
            con.execute(
                """INSERT OR REPLACE INTO products
                   (id, name, description, owner, business_unit, target_market,
                    status, current_stage, tags, created_at, launched_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    product.id,
                    product.name,
                    product.description,
                    product.owner,
                    product.business_unit,
                    product.target_market,
                    product.status.value,
                    product.current_stage.value,
                    json.dumps(product.tags),
                    product.created_at.isoformat(),
                    product.launched_at.isoformat() if product.launched_at else None,
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

    def list_products(self, status: Optional[ProductStatus] = None) -> list[Product]:
        with _conn(self.db_path) as con:
            if status:
                rows = con.execute(
                    "SELECT * FROM products WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM products ORDER BY created_at DESC"
                ).fetchall()
            return [self._hydrate_product(con, r) for r in rows]

    def delete_product(self, product_id: str) -> bool:
        with _conn(self.db_path) as con:
            cur = con.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return cur.rowcount > 0

    def _hydrate_product(self, con: sqlite3.Connection, row: sqlite3.Row) -> Product:
        stages_rows = con.execute(
            "SELECT * FROM stages WHERE product_id = ? ORDER BY rowid", (row["id"],)
        ).fetchall()
        stages = [self._hydrate_stage(con, sr) for sr in stages_rows]
        return Product(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            owner=row["owner"],
            business_unit=row["business_unit"],
            target_market=row["target_market"],
            status=ProductStatus(row["status"]),
            current_stage=StageName(row["current_stage"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            launched_at=_parse_dt(row["launched_at"]),
            stages=stages,
            tags=json.loads(row["tags"]),
        )

    # ── Stages ────────────────────────────────────────────────────────────────

    def save_stage(self, stage: Stage) -> None:
        with _conn(self.db_path) as con:
            con.execute(
                """INSERT OR REPLACE INTO stages
                   (id, product_id, name, status, owner, target_date,
                    completed_at, notes, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    stage.id,
                    stage.product_id,
                    stage.name.value,
                    stage.status.value,
                    stage.owner,
                    stage.target_date.isoformat() if stage.target_date else None,
                    stage.completed_at.isoformat() if stage.completed_at else None,
                    stage.notes,
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
            return self._hydrate_stage(con, row)

    def _hydrate_stage(self, con: sqlite3.Connection, row: sqlite3.Row) -> Stage:
        task_rows = con.execute(
            "SELECT * FROM tasks WHERE stage_id = ? ORDER BY rowid", (row["id"],)
        ).fetchall()
        gate_rows = con.execute(
            "SELECT * FROM gate_criteria WHERE stage_id = ? ORDER BY rowid",
            (row["id"],),
        ).fetchall()
        tasks = [
            Task(
                id=tr["id"],
                stage_id=tr["stage_id"],
                title=tr["title"],
                description=tr["description"],
                owner=tr["owner"],
                priority=TaskPriority(tr["priority"]),
                status=TaskStatus(tr["status"]),
                due_date=_parse_date(tr["due_date"]),
                completed_at=_parse_dt(tr["completed_at"]),
                created_at=datetime.fromisoformat(tr["created_at"]),
                notes=tr["notes"],
            )
            for tr in task_rows
        ]
        gates = [
            GateCriterion(
                id=gr["id"],
                stage_id=gr["stage_id"],
                description=gr["description"],
                is_met=bool(gr["is_met"]),
                verified_by=gr["verified_by"],
                verified_at=_parse_dt(gr["verified_at"]),
            )
            for gr in gate_rows
        ]
        return Stage(
            id=row["id"],
            product_id=row["product_id"],
            name=StageName(row["name"]),
            status=StageStatus(row["status"]),
            owner=row["owner"],
            target_date=_parse_date(row["target_date"]),
            completed_at=_parse_dt(row["completed_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            tasks=tasks,
            gate_criteria=gates,
            notes=row["notes"],
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def save_task(self, task: Task) -> None:
        with _conn(self.db_path) as con:
            con.execute(
                """INSERT OR REPLACE INTO tasks
                   (id, stage_id, title, description, owner, priority,
                    status, due_date, completed_at, notes, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task.id,
                    task.stage_id,
                    task.title,
                    task.description,
                    task.owner,
                    task.priority.value,
                    task.status.value,
                    task.due_date.isoformat() if task.due_date else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.notes,
                    task.created_at.isoformat(),
                ),
            )

    def get_task(self, task_id: str) -> Optional[Task]:
        with _conn(self.db_path) as con:
            row = con.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            return Task(
                id=row["id"],
                stage_id=row["stage_id"],
                title=row["title"],
                description=row["description"],
                owner=row["owner"],
                priority=TaskPriority(row["priority"]),
                status=TaskStatus(row["status"]),
                due_date=_parse_date(row["due_date"]),
                completed_at=_parse_dt(row["completed_at"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                notes=row["notes"],
            )

    # ── Gate Criteria ─────────────────────────────────────────────────────────

    def save_gate(self, gate: GateCriterion) -> None:
        with _conn(self.db_path) as con:
            con.execute(
                """INSERT OR REPLACE INTO gate_criteria
                   (id, stage_id, description, is_met, verified_by, verified_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    gate.id,
                    gate.stage_id,
                    gate.description,
                    int(gate.is_met),
                    gate.verified_by,
                    gate.verified_at.isoformat() if gate.verified_at else None,
                ),
            )

    def get_gate(self, gate_id: str) -> Optional[GateCriterion]:
        with _conn(self.db_path) as con:
            row = con.execute(
                "SELECT * FROM gate_criteria WHERE id = ?", (gate_id,)
            ).fetchone()
            if not row:
                return None
            return GateCriterion(
                id=row["id"],
                stage_id=row["stage_id"],
                description=row["description"],
                is_met=bool(row["is_met"]),
                verified_by=row["verified_by"],
                verified_at=_parse_dt(row["verified_at"]),
            )
