"""Tests for Anton data models and database layer."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from anton.db import AntonDB
from anton.models import (
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
from anton.stages import STAGE_TEMPLATES, STAGE_TEMPLATE_MAP


# ── Model unit tests ──────────────────────────────────────────────────────────


def test_product_create_defaults():
    p = Product.create(name="Widget X", description="A great widget", owner="alice")
    assert p.name == "Widget X"
    assert p.owner == "alice"
    assert p.status == ProductStatus.ACTIVE
    assert p.current_stage == StageName.IDEATION
    assert p.overall_progress == 0.0
    assert p.id  # UUID assigned


def test_stage_task_completion():
    product = Product.create(name="Test", description="", owner="bob")
    stage = Stage.create(product_id=product.id, name=StageName.IDEATION)

    t1 = Task.create(stage_id=stage.id, title="Task A")
    t2 = Task.create(stage_id=stage.id, title="Task B")
    t2.status = TaskStatus.DONE

    stage.tasks = [t1, t2]
    assert stage.task_completion_pct == 50.0


def test_stage_gate_readiness():
    product = Product.create(name="Test", description="", owner="bob")
    stage = Stage.create(product_id=product.id, name=StageName.MARKET_RESEARCH)

    g1 = GateCriterion.create(stage_id=stage.id, description="Interviews done")
    g2 = GateCriterion.create(stage_id=stage.id, description="Analysis complete")
    g1.is_met = True

    stage.gate_criteria = [g1, g2]
    assert not stage.is_gate_ready
    assert stage.gate_completion_pct == 50.0

    g2.is_met = True
    assert stage.is_gate_ready


def test_product_overall_progress_with_stages():
    product = Product.create(name="Test", description="", owner="carol")
    # Simulate: ideation completed, market_research in-progress with 50% tasks done
    s1 = Stage.create(product_id=product.id, name=StageName.IDEATION)
    s1.status = StageStatus.COMPLETED

    s2 = Stage.create(product_id=product.id, name=StageName.MARKET_RESEARCH)
    t1 = Task.create(stage_id=s2.id, title="T1")
    t1.status = TaskStatus.DONE
    t2 = Task.create(stage_id=s2.id, title="T2")
    s2.tasks = [t1, t2]

    product.stages = [s1, s2]
    product.current_stage = StageName.MARKET_RESEARCH

    total = len(list(StageName))  # 7
    # completed_stages=1, current_progress=0.5 → (1+0.5)/7 * 100
    expected = round(1.5 / total * 100, 1)
    assert product.overall_progress == expected


def test_stage_templates_completeness():
    """All 7 stages must have templates."""
    assert len(STAGE_TEMPLATES) == len(list(StageName))
    for stage_name in StageName:
        assert stage_name in STAGE_TEMPLATE_MAP
        tmpl = STAGE_TEMPLATE_MAP[stage_name]
        assert len(tmpl.tasks) > 0, f"{stage_name} has no task templates"
        assert len(tmpl.gate_criteria) > 0, f"{stage_name} has no gate criteria"


# ── Database integration tests ────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    return AntonDB(db_path=tmp_path / "test.db")


def test_save_and_get_product(db):
    p = Product.create(name="Alpha", description="First product", owner="dave")
    db.save_product(p)

    fetched = db.get_product(p.id)
    assert fetched is not None
    assert fetched.name == "Alpha"
    assert fetched.owner == "dave"
    assert fetched.status == ProductStatus.ACTIVE


def test_save_stage_with_tasks_and_gates(db):
    product = Product.create(name="Beta", description="", owner="eve")
    db.save_product(product)

    stage = Stage.create(product_id=product.id, name=StageName.IDEATION)
    db.save_stage(stage)

    task = Task.create(stage_id=stage.id, title="Draft concept", priority=TaskPriority.HIGH)
    db.save_task(task)

    gate = GateCriterion.create(stage_id=stage.id, description="Concept approved")
    db.save_gate(gate)

    fetched_stage = db.get_stage(stage.id)
    assert fetched_stage is not None
    assert len(fetched_stage.tasks) == 1
    assert fetched_stage.tasks[0].title == "Draft concept"
    assert len(fetched_stage.gate_criteria) == 1
    assert not fetched_stage.gate_criteria[0].is_met


def test_list_products_filter(db):
    p1 = Product.create(name="Active One", description="", owner="frank")
    p2 = Product.create(name="Held One", description="", owner="frank")
    p2.status = ProductStatus.ON_HOLD

    db.save_product(p1)
    db.save_product(p2)

    active = db.list_products(status=ProductStatus.ACTIVE)
    assert len(active) == 1
    assert active[0].name == "Active One"

    all_prods = db.list_products()
    assert len(all_prods) == 2


def test_product_hydration_includes_stages(db):
    product = Product.create(name="Gamma", description="", owner="grace")
    db.save_product(product)

    for tmpl in STAGE_TEMPLATES:
        stage = Stage.create(product_id=product.id, name=tmpl.name)
        db.save_stage(stage)
        for t in tmpl.tasks:
            db.save_task(Task.create(stage_id=stage.id, title=t.title))
        for g in tmpl.gate_criteria:
            db.save_gate(GateCriterion.create(stage_id=stage.id, description=g))

    fetched = db.get_product(product.id)
    assert fetched is not None
    assert len(fetched.stages) == 7
    for stage in fetched.stages:
        assert len(stage.tasks) > 0


def test_task_update_status(db):
    product = Product.create(name="Delta", description="", owner="henry")
    db.save_product(product)
    stage = Stage.create(product_id=product.id, name=StageName.IDEATION)
    db.save_stage(stage)

    task = Task.create(stage_id=stage.id, title="Do research")
    db.save_task(task)

    task.status = TaskStatus.DONE
    from datetime import datetime
    task.completed_at = datetime.utcnow()
    db.save_task(task)

    fetched = db.get_task(task.id)
    assert fetched is not None
    assert fetched.status == TaskStatus.DONE
    assert fetched.completed_at is not None


def test_delete_product_cascades(db):
    product = Product.create(name="Epsilon", description="", owner="irene")
    db.save_product(product)
    stage = Stage.create(product_id=product.id, name=StageName.IDEATION)
    db.save_stage(stage)
    task = Task.create(stage_id=stage.id, title="Task X")
    db.save_task(task)

    deleted = db.delete_product(product.id)
    assert deleted

    assert db.get_product(product.id) is None
    assert db.get_stage(stage.id) is None
    assert db.get_task(task.id) is None
