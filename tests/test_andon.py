"""Tests for the Andon commercialization alert system."""

from __future__ import annotations

from datetime import datetime

import pytest

from andon.db import AndonDB
from andon.models import (
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


# ── Model unit tests ──────────────────────────────────────────────────────────


def test_product_create_defaults():
    p = Product.create(name="Widget X", owner="alice")
    assert p.name == "Widget X"
    assert p.owner == "alice"
    assert p.current_stage == StageName.IDEATION
    assert p.open_signals == []
    assert p.andon_color == "green"
    assert p.id


def test_andon_color_green_when_no_open_signals():
    p = Product.create(name="P", owner="a")
    assert p.andon_color == "green"


def test_andon_color_yellow_for_warning():
    p = Product.create(name="P", owner="a")
    sig = AndonSignal.create(
        product_id=p.id,
        stage_name=StageName.IDEATION,
        title="Minor issue",
        description="",
        raised_by="alice",
        severity=SignalSeverity.WARNING,
    )
    p.signals = [sig]
    assert p.andon_color == "yellow"


def test_andon_color_red_for_critical():
    p = Product.create(name="P", owner="a")
    sig = AndonSignal.create(
        product_id=p.id,
        stage_name=StageName.IDEATION,
        title="Bad bug",
        description="",
        raised_by="alice",
        severity=SignalSeverity.CRITICAL,
    )
    p.signals = [sig]
    assert p.andon_color == "red"


def test_andon_color_stop_overrides_critical():
    p = Product.create(name="P", owner="a")
    critical_sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.IDEATION,
        title="Critical", description="", raised_by="a", severity=SignalSeverity.CRITICAL,
    )
    stop_sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.IDEATION,
        title="STOP", description="", raised_by="b", severity=SignalSeverity.STOP,
    )
    p.signals = [critical_sig, stop_sig]
    assert p.andon_color == "stop"


def test_resolved_signal_not_counted_as_open():
    p = Product.create(name="P", owner="a")
    sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.IDEATION,
        title="Fixed", description="", raised_by="a",
    )
    sig.status = SignalStatus.RESOLVED
    p.signals = [sig]
    assert p.open_signals == []
    assert p.andon_color == "green"


def test_signal_age_hours():
    sig = AndonSignal.create(
        product_id="x", stage_name=StageName.IDEATION,
        title="T", description="", raised_by="a",
    )
    assert sig.age_hours >= 0.0
    assert sig.age_hours < 1.0


def test_escalation_event_create():
    event = EscalationEvent.create(
        signal_id="sig-1",
        from_level=EscalationLevel.TEAM,
        to_level=EscalationLevel.MANAGER,
        escalated_by="bob",
        reason="Unacknowledged for 24h",
    )
    assert event.from_level == EscalationLevel.TEAM
    assert event.to_level == EscalationLevel.MANAGER
    assert event.escalated_by == "bob"


# ── DB integration tests ──────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    return AndonDB(db_path=tmp_path / "test.db")


def test_save_and_get_product(db):
    p = Product.create(name="Alpha", owner="dave")
    db.save_product(p)
    fetched = db.get_product(p.id)
    assert fetched is not None
    assert fetched.name == "Alpha"
    assert fetched.owner == "dave"


def test_product_with_stages(db):
    p = Product.create(name="Beta", owner="eve")
    db.save_product(p)
    for name in StageName:
        db.save_stage(Stage.create(product_id=p.id, name=name))

    fetched = db.get_product(p.id)
    assert fetched is not None
    assert len(fetched.stages) == 7


def test_save_and_get_signal(db):
    p = Product.create(name="Gamma", owner="frank")
    db.save_product(p)

    sig = AndonSignal.create(
        product_id=p.id,
        stage_name=StageName.MARKET_RESEARCH,
        title="Customer data unavailable",
        description="CRM access revoked",
        raised_by="grace",
        severity=SignalSeverity.CRITICAL,
        category=SignalCategory.RESOURCE,
    )
    db.save_signal(sig)

    fetched = db.get_signal(sig.id)
    assert fetched is not None
    assert fetched.title == "Customer data unavailable"
    assert fetched.severity == SignalSeverity.CRITICAL
    assert fetched.category == SignalCategory.RESOURCE
    assert fetched.status == SignalStatus.OPEN
    assert fetched.escalation_level == EscalationLevel.TEAM


def test_signal_lifecycle(db):
    p = Product.create(name="Delta", owner="henry")
    db.save_product(p)

    sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.BUSINESS_CASE,
        title="No budget approval", description="", raised_by="irene",
    )
    db.save_signal(sig)

    # Acknowledge
    sig.status = SignalStatus.ACKNOWLEDGED
    sig.acknowledged_by = "james"
    sig.acknowledged_at = datetime.utcnow()
    db.save_signal(sig)

    fetched = db.get_signal(sig.id)
    assert fetched.status == SignalStatus.ACKNOWLEDGED
    assert fetched.acknowledged_by == "james"

    # Resolve
    sig.status = SignalStatus.RESOLVED
    sig.resolved_by = "james"
    sig.resolved_at = datetime.utcnow()
    sig.root_cause = "Finance team on holiday"
    sig.corrective_action = "Scheduled emergency review"
    db.save_signal(sig)

    fetched = db.get_signal(sig.id)
    assert fetched.status == SignalStatus.RESOLVED
    assert fetched.root_cause == "Finance team on holiday"
    assert not fetched.is_open


def test_escalation_persisted(db):
    p = Product.create(name="Epsilon", owner="kate")
    db.save_product(p)
    sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.PRODUCT_DEVELOPMENT,
        title="Build failing", description="", raised_by="leo",
        severity=SignalSeverity.CRITICAL,
    )
    db.save_signal(sig)

    event = EscalationEvent.create(
        signal_id=sig.id,
        from_level=EscalationLevel.TEAM,
        to_level=EscalationLevel.MANAGER,
        escalated_by="leo",
        reason="Unresolved for 48h",
    )
    db.save_escalation(event)

    sig.escalation_level = EscalationLevel.MANAGER
    sig.status = SignalStatus.ESCALATED
    db.save_signal(sig)

    fetched = db.get_signal(sig.id)
    assert fetched.escalation_level == EscalationLevel.MANAGER
    assert fetched.status == SignalStatus.ESCALATED
    assert len(fetched.escalation_history) == 1
    assert fetched.escalation_history[0].to_level == EscalationLevel.MANAGER


def test_list_signals_filters(db):
    p = Product.create(name="Zeta", owner="mia")
    db.save_product(p)

    open_sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.IDEATION,
        title="Open issue", description="", raised_by="mia",
        severity=SignalSeverity.WARNING,
    )
    resolved_sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.IDEATION,
        title="Resolved issue", description="", raised_by="mia",
        severity=SignalSeverity.INFO,
    )
    resolved_sig.status = SignalStatus.RESOLVED
    db.save_signal(open_sig)
    db.save_signal(resolved_sig)

    open_list = db.list_signals(status=SignalStatus.OPEN)
    assert len(open_list) == 1
    assert open_list[0].title == "Open issue"

    warning_list = db.list_signals(severity=SignalSeverity.WARNING)
    assert len(warning_list) == 1

    all_for_product = db.list_signals(product_id=p.id)
    assert len(all_for_product) == 2


def test_delete_product_cascades_signals(db):
    p = Product.create(name="Eta", owner="noah")
    db.save_product(p)
    sig = AndonSignal.create(
        product_id=p.id, stage_name=StageName.IDEATION,
        title="To be deleted", description="", raised_by="noah",
    )
    db.save_signal(sig)

    db.delete_product(p.id)
    assert db.get_product(p.id) is None
    assert db.get_signal(sig.id) is None


def test_product_hydration_includes_signals(db):
    p = Product.create(name="Theta", owner="olivia")
    db.save_product(p)

    for i in range(3):
        sig = AndonSignal.create(
            product_id=p.id, stage_name=StageName.GO_TO_MARKET,
            title=f"Signal {i}", description="", raised_by="olivia",
        )
        db.save_signal(sig)

    fetched = db.get_product(p.id)
    assert fetched is not None
    assert len(fetched.signals) == 3
    assert fetched.andon_color == "yellow"  # all are warnings by default
