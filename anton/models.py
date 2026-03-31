"""Data models for the Anton commercialization system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class ProductStatus(str, Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    LAUNCHED = "launched"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StageName(str, Enum):
    IDEATION = "ideation"
    MARKET_RESEARCH = "market_research"
    BUSINESS_CASE = "business_case"
    PRODUCT_DEVELOPMENT = "product_development"
    LAUNCH_PREPARATION = "launch_preparation"
    GO_TO_MARKET = "go_to_market"
    POST_LAUNCH_REVIEW = "post_launch_review"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()

    @property
    def order(self) -> int:
        return list(StageName).index(self)


@dataclass
class Task:
    id: str
    stage_id: str
    title: str
    description: str
    owner: Optional[str]
    priority: TaskPriority
    status: TaskStatus
    due_date: Optional[date]
    completed_at: Optional[datetime]
    created_at: datetime
    notes: Optional[str] = None

    @classmethod
    def create(
        cls,
        stage_id: str,
        title: str,
        description: str = "",
        owner: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[date] = None,
    ) -> "Task":
        return cls(
            id=str(uuid.uuid4()),
            stage_id=stage_id,
            title=title,
            description=description,
            owner=owner,
            priority=priority,
            status=TaskStatus.OPEN,
            due_date=due_date,
            completed_at=None,
            created_at=datetime.utcnow(),
        )


@dataclass
class GateCriterion:
    id: str
    stage_id: str
    description: str
    is_met: bool
    verified_by: Optional[str]
    verified_at: Optional[datetime]

    @classmethod
    def create(cls, stage_id: str, description: str) -> "GateCriterion":
        return cls(
            id=str(uuid.uuid4()),
            stage_id=stage_id,
            description=description,
            is_met=False,
            verified_by=None,
            verified_at=None,
        )


@dataclass
class Stage:
    id: str
    product_id: str
    name: StageName
    status: StageStatus
    owner: Optional[str]
    target_date: Optional[date]
    completed_at: Optional[datetime]
    created_at: datetime
    tasks: list[Task] = field(default_factory=list)
    gate_criteria: list[GateCriterion] = field(default_factory=list)
    notes: Optional[str] = None

    @classmethod
    def create(
        cls,
        product_id: str,
        name: StageName,
        owner: Optional[str] = None,
        target_date: Optional[date] = None,
    ) -> "Stage":
        return cls(
            id=str(uuid.uuid4()),
            product_id=product_id,
            name=name,
            status=StageStatus.NOT_STARTED,
            owner=owner,
            target_date=target_date,
            completed_at=None,
            created_at=datetime.utcnow(),
        )

    @property
    def task_completion_pct(self) -> float:
        if not self.tasks:
            return 0.0
        done = sum(1 for t in self.tasks if t.status == TaskStatus.DONE)
        return round(done / len(self.tasks) * 100, 1)

    @property
    def gate_completion_pct(self) -> float:
        if not self.gate_criteria:
            return 0.0
        met = sum(1 for g in self.gate_criteria if g.is_met)
        return round(met / len(self.gate_criteria) * 100, 1)

    @property
    def is_gate_ready(self) -> bool:
        return all(g.is_met for g in self.gate_criteria)


@dataclass
class Product:
    id: str
    name: str
    description: str
    owner: str
    business_unit: Optional[str]
    target_market: Optional[str]
    status: ProductStatus
    current_stage: StageName
    created_at: datetime
    launched_at: Optional[datetime]
    stages: list[Stage] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        owner: str,
        business_unit: Optional[str] = None,
        target_market: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> "Product":
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            owner=owner,
            business_unit=business_unit,
            target_market=target_market,
            status=ProductStatus.ACTIVE,
            current_stage=StageName.IDEATION,
            created_at=datetime.utcnow(),
            launched_at=None,
            tags=tags or [],
        )

    def get_stage(self, name: StageName) -> Optional[Stage]:
        for s in self.stages:
            if s.name == name:
                return s
        return None

    @property
    def overall_progress(self) -> float:
        """Weighted progress across completed + current stage tasks."""
        if not self.stages:
            return 0.0
        total_stages = len(StageName)
        completed_stages = sum(
            1 for s in self.stages if s.status == StageStatus.COMPLETED
        )
        current = self.get_stage(self.current_stage)
        current_progress = (current.task_completion_pct / 100) if current else 0.0
        return round((completed_stages + current_progress) / total_stages * 100, 1)
