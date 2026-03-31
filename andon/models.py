"""Data models for the Andon commercialization alert system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SignalSeverity(str, Enum):
    """Severity levels mirror the classic Andon light colours."""
    INFO = "info"          # Blue  – informational, no action required immediately
    WARNING = "warning"    # Yellow – issue may delay progress; needs attention
    CRITICAL = "critical"  # Red   – work is stopped or at high risk of stopping
    STOP = "stop"          # Flashing red – full stoppage; immediate escalation


class SignalCategory(str, Enum):
    QUALITY = "quality"            # Product/process quality defect
    BLOCKER = "blocker"            # Dependency or technical blocker
    RESOURCE = "resource"          # People, budget, or tooling shortage
    DECISION = "decision"          # Awaiting a decision to proceed
    RISK = "risk"                  # Identified risk that may impact schedule/scope
    COMPLIANCE = "compliance"      # Regulatory or legal concern


class SignalStatus(str, Enum):
    OPEN = "open"                  # Raised but unacknowledged
    ACKNOWLEDGED = "acknowledged"  # Someone has taken ownership
    RESOLVED = "resolved"          # Issue closed with root cause documented
    ESCALATED = "escalated"        # Pushed up the chain due to inaction / severity


class EscalationLevel(int, Enum):
    TEAM = 0          # Visible to immediate team
    MANAGER = 1       # Escalated to line manager
    DIRECTOR = 2      # Escalated to director/VP
    EXECUTIVE = 3     # Executive attention required


class StageStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"      # Andon cord pulled on this stage
    COMPLETED = "completed"


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
class EscalationEvent:
    """Records a single escalation step for an Andon signal."""
    id: str
    signal_id: str
    from_level: EscalationLevel
    to_level: EscalationLevel
    escalated_by: str
    reason: str
    escalated_at: datetime

    @classmethod
    def create(
        cls,
        signal_id: str,
        from_level: EscalationLevel,
        to_level: EscalationLevel,
        escalated_by: str,
        reason: str,
    ) -> "EscalationEvent":
        return cls(
            id=str(uuid.uuid4()),
            signal_id=signal_id,
            from_level=from_level,
            to_level=to_level,
            escalated_by=escalated_by,
            reason=reason,
            escalated_at=datetime.utcnow(),
        )


@dataclass
class AndonSignal:
    """
    Core model — represents an Andon cord pull in the commercialization process.

    A signal is raised when any team member detects a problem that threatens
    the product introduction timeline or quality. It must be acknowledged and
    resolved, with root cause documented to enable continuous improvement.
    """
    id: str
    product_id: str
    stage_name: StageName
    severity: SignalSeverity
    category: SignalCategory
    status: SignalStatus
    title: str
    description: str
    raised_by: str
    raised_at: datetime
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    root_cause: Optional[str]           # Filled on resolution — feeds 5-Why / Kaizen
    corrective_action: Optional[str]    # What was done to fix it
    escalation_level: EscalationLevel
    escalation_history: list[EscalationEvent] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        product_id: str,
        stage_name: StageName,
        title: str,
        description: str,
        raised_by: str,
        severity: SignalSeverity = SignalSeverity.WARNING,
        category: SignalCategory = SignalCategory.BLOCKER,
        tags: Optional[list[str]] = None,
    ) -> "AndonSignal":
        return cls(
            id=str(uuid.uuid4()),
            product_id=product_id,
            stage_name=stage_name,
            severity=severity,
            category=category,
            status=SignalStatus.OPEN,
            title=title,
            description=description,
            raised_by=raised_by,
            raised_at=datetime.utcnow(),
            acknowledged_by=None,
            acknowledged_at=None,
            resolved_by=None,
            resolved_at=None,
            root_cause=None,
            corrective_action=None,
            escalation_level=EscalationLevel.TEAM,
            tags=tags or [],
        )

    @property
    def age_hours(self) -> float:
        end = self.resolved_at or datetime.utcnow()
        return round((end - self.raised_at).total_seconds() / 3600, 1)

    @property
    def is_open(self) -> bool:
        return self.status in (SignalStatus.OPEN, SignalStatus.ACKNOWLEDGED, SignalStatus.ESCALATED)


@dataclass
class Stage:
    id: str
    product_id: str
    name: StageName
    status: StageStatus
    owner: Optional[str]
    created_at: datetime

    @classmethod
    def create(cls, product_id: str, name: StageName, owner: Optional[str] = None) -> "Stage":
        return cls(
            id=str(uuid.uuid4()),
            product_id=product_id,
            name=name,
            status=StageStatus.NOT_STARTED,
            owner=owner,
            created_at=datetime.utcnow(),
        )


@dataclass
class Product:
    id: str
    name: str
    owner: str
    business_unit: Optional[str]
    current_stage: StageName
    created_at: datetime
    stages: list[Stage] = field(default_factory=list)
    signals: list[AndonSignal] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        owner: str,
        business_unit: Optional[str] = None,
    ) -> "Product":
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            owner=owner,
            business_unit=business_unit,
            current_stage=StageName.IDEATION,
            created_at=datetime.utcnow(),
        )

    @property
    def open_signals(self) -> list[AndonSignal]:
        return [s for s in self.signals if s.is_open]

    @property
    def andon_color(self) -> str:
        """
        Derive the Andon board colour for this product from its open signals.
        Green  → no open signals
        Blue   → open INFO signals only
        Yellow → open WARNING signals
        Red    → open CRITICAL signal
        Stop   → open STOP signal (full stoppage)
        """
        open_sigs = self.open_signals
        if not open_sigs:
            return "green"
        severities = {s.severity for s in open_sigs}
        if SignalSeverity.STOP in severities:
            return "stop"
        if SignalSeverity.CRITICAL in severities:
            return "red"
        if SignalSeverity.WARNING in severities:
            return "yellow"
        return "blue"
