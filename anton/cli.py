"""Anton CLI - Commercialization Process Management."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box

from .db import AntonDB
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
from .stages import STAGE_TEMPLATES, STAGE_TEMPLATE_MAP

app = typer.Typer(
    name="anton",
    help="Anton - Commercialization Process Management for New Product Introductions",
    no_args_is_help=True,
)
product_app = typer.Typer(help="Manage products in the commercialization pipeline.")
stage_app = typer.Typer(help="Manage commercialization stages.")
task_app = typer.Typer(help="Manage tasks within stages.")

app.add_typer(product_app, name="product")
app.add_typer(stage_app, name="stage")
app.add_typer(task_app, name="task")

console = Console()
err_console = Console(stderr=True)

_DB_PATH_OPT = typer.Option(None, "--db", help="Path to Anton database file.")


def _get_db(db_path: Optional[Path]) -> AntonDB:
    return AntonDB(db_path) if db_path else AntonDB()


def _abort(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/] {msg}")
    raise typer.Exit(1)


def _find_product(db: AntonDB, id_or_name: str) -> Product:
    product = db.get_product(id_or_name)
    if not product:
        # Try partial name match
        all_products = db.list_products()
        matches = [p for p in all_products if id_or_name.lower() in p.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            _abort(
                f"'{id_or_name}' matches multiple products. Use the product ID instead."
            )
        _abort(f"Product '{id_or_name}' not found.")
    return product  # type: ignore[return-value]


def _status_color(status: str) -> str:
    colors = {
        "active": "green",
        "on_hold": "yellow",
        "launched": "blue",
        "cancelled": "red",
        "not_started": "dim",
        "in_progress": "cyan",
        "completed": "green",
        "blocked": "red",
        "skipped": "dim",
        "open": "white",
        "done": "green",
    }
    return colors.get(status, "white")


def _priority_color(priority: str) -> str:
    return {"low": "dim", "medium": "white", "high": "yellow", "critical": "bold red"}.get(
        priority, "white"
    )


# ── Product commands ──────────────────────────────────────────────────────────


@product_app.command("new")
def product_new(
    name: str = typer.Argument(..., help="Product name"),
    owner: str = typer.Option(..., "--owner", "-o", help="Product owner / PM"),
    description: str = typer.Option("", "--description", "-d", help="Short description"),
    business_unit: Optional[str] = typer.Option(None, "--bu", help="Business unit"),
    target_market: Optional[str] = typer.Option(None, "--market", help="Target market"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    with_stages: bool = typer.Option(True, help="Auto-create all 7 stages with default tasks"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Create a new product and initialize its commercialization pipeline."""
    db = _get_db(db_path)
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    product = Product.create(
        name=name,
        description=description,
        owner=owner,
        business_unit=business_unit,
        target_market=target_market,
        tags=tag_list,
    )
    db.save_product(product)

    if with_stages:
        for tmpl in STAGE_TEMPLATES:
            stage = Stage.create(product_id=product.id, name=tmpl.name, owner=owner)
            db.save_stage(stage)
            for task_tmpl in tmpl.tasks:
                task = Task.create(
                    stage_id=stage.id,
                    title=task_tmpl.title,
                    description=task_tmpl.description,
                    priority=task_tmpl.priority,
                )
                db.save_task(task)
            for criterion in tmpl.gate_criteria:
                gate = GateCriterion.create(stage_id=stage.id, description=criterion)
                db.save_gate(gate)

    console.print(
        f"\n[bold green]Product created:[/] [cyan]{product.name}[/] [dim](ID: {product.id[:8]}...)[/]"
    )
    if with_stages:
        console.print(
            f"  [dim]Initialized {len(STAGE_TEMPLATES)} stages with default tasks and gate criteria.[/]"
        )
    console.print(f"  Run [bold]anton product show {product.id[:8]}[/] to view details.\n")


@product_app.command("list")
def product_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """List all products in the pipeline."""
    db = _get_db(db_path)
    filter_status = ProductStatus(status) if status else None
    products = db.list_products(filter_status)

    if not products:
        console.print("[dim]No products found.[/]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Product", min_width=20)
    table.add_column("Owner")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Progress", justify="right")
    table.add_column("BU")

    for p in products:
        color = _status_color(p.status.value)
        table.add_row(
            p.id[:8],
            p.name,
            p.owner,
            p.current_stage.display_name,
            f"[{color}]{p.status.value}[/]",
            f"{p.overall_progress}%",
            p.business_unit or "",
        )

    console.print(f"\n[bold]Products[/] ({len(products)} total)\n")
    console.print(table)
    console.print()


@product_app.command("show")
def product_show(
    id_or_name: str = typer.Argument(..., help="Product ID (or partial name)"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Show full details for a product including all stages."""
    db = _get_db(db_path)
    product = _find_product(db, id_or_name)
    _render_product(product)


@product_app.command("update")
def product_update(
    id_or_name: str = typer.Argument(..., help="Product ID or name"),
    status: Optional[str] = typer.Option(None, "--status", help="New status"),
    owner: Optional[str] = typer.Option(None, "--owner"),
    description: Optional[str] = typer.Option(None, "--description"),
    business_unit: Optional[str] = typer.Option(None, "--bu"),
    target_market: Optional[str] = typer.Option(None, "--market"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Update product metadata."""
    db = _get_db(db_path)
    product = _find_product(db, id_or_name)

    if status:
        product.status = ProductStatus(status)
        if status == "launched" and not product.launched_at:
            product.launched_at = datetime.utcnow()
    if owner:
        product.owner = owner
    if description:
        product.description = description
    if business_unit:
        product.business_unit = business_unit
    if target_market:
        product.target_market = target_market

    db.save_product(product)
    console.print(f"[green]Updated[/] product [cyan]{product.name}[/].")


@product_app.command("advance")
def product_advance(
    id_or_name: str = typer.Argument(..., help="Product ID or name"),
    force: bool = typer.Option(False, "--force", "-f", help="Advance even if gate not met"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Advance a product to the next commercialization stage."""
    db = _get_db(db_path)
    product = _find_product(db, id_or_name)

    stage_order = list(StageName)
    current_idx = stage_order.index(product.current_stage)

    if current_idx >= len(stage_order) - 1:
        _abort("Product is already at the final stage (Post-Launch Review).")

    current_stage = product.get_stage(product.current_stage)
    if current_stage and not current_stage.is_gate_ready and not force:
        unmet = [g.description for g in current_stage.gate_criteria if not g.is_met]
        console.print("[bold yellow]Gate criteria not fully met:[/]")
        for u in unmet:
            console.print(f"  [red]✗[/] {u}")
        if not Confirm.ask("\nAdvance anyway?"):
            raise typer.Exit(0)

    # Mark current stage complete
    if current_stage:
        current_stage.status = StageStatus.COMPLETED
        current_stage.completed_at = datetime.utcnow()
        db.save_stage(current_stage)

    next_stage_name = stage_order[current_idx + 1]
    product.current_stage = next_stage_name

    # Mark next stage in-progress
    next_stage = product.get_stage(next_stage_name)
    if next_stage:
        next_stage.status = StageStatus.IN_PROGRESS
        db.save_stage(next_stage)

    db.save_product(product)
    console.print(
        f"[green]Advanced[/] [cyan]{product.name}[/] to [bold]{next_stage_name.display_name}[/]."
    )


# ── Stage commands ────────────────────────────────────────────────────────────


@stage_app.command("show")
def stage_show(
    stage_id: str = typer.Argument(..., help="Stage ID"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Show full details for a stage including tasks and gate criteria."""
    db = _get_db(db_path)
    stage = db.get_stage(stage_id)
    if not stage:
        _abort(f"Stage '{stage_id}' not found.")
    _render_stage(stage)


@stage_app.command("update")
def stage_update(
    stage_id: str = typer.Argument(..., help="Stage ID"),
    status: Optional[str] = typer.Option(None, "--status"),
    owner: Optional[str] = typer.Option(None, "--owner"),
    target_date: Optional[str] = typer.Option(None, "--target-date", help="YYYY-MM-DD"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Update stage metadata."""
    db = _get_db(db_path)
    stage = db.get_stage(stage_id)
    if not stage:
        _abort(f"Stage '{stage_id}' not found.")

    if status:
        stage.status = StageStatus(status)
        if status == "completed" and not stage.completed_at:
            stage.completed_at = datetime.utcnow()
    if owner:
        stage.owner = owner
    if target_date:
        stage.target_date = date.fromisoformat(target_date)
    if notes:
        stage.notes = notes

    db.save_stage(stage)
    console.print(f"[green]Updated[/] stage [cyan]{stage.name.display_name}[/].")


@stage_app.command("gate")
def stage_gate(
    gate_id: str = typer.Argument(..., help="Gate criterion ID"),
    met: bool = typer.Option(..., "--met/--not-met", help="Mark criterion as met or not"),
    verified_by: Optional[str] = typer.Option(None, "--by", help="Who verified this"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Mark a gate criterion as met or not met."""
    db = _get_db(db_path)
    gate = db.get_gate(gate_id)
    if not gate:
        _abort(f"Gate criterion '{gate_id}' not found.")

    gate.is_met = met
    gate.verified_by = verified_by
    gate.verified_at = datetime.utcnow() if met else None
    db.save_gate(gate)

    symbol = "[green]✓[/]" if met else "[red]✗[/]"
    console.print(f"{symbol} Gate criterion updated.")


# ── Task commands ─────────────────────────────────────────────────────────────


@task_app.command("new")
def task_new(
    stage_id: str = typer.Argument(..., help="Stage ID to add the task to"),
    title: str = typer.Option(..., "--title", "-t"),
    description: str = typer.Option("", "--description", "-d"),
    owner: Optional[str] = typer.Option(None, "--owner", "-o"),
    priority: str = typer.Option("medium", "--priority", "-p"),
    due_date: Optional[str] = typer.Option(None, "--due", help="YYYY-MM-DD"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Add a new task to a stage."""
    db = _get_db(db_path)
    stage = db.get_stage(stage_id)
    if not stage:
        _abort(f"Stage '{stage_id}' not found.")

    task = Task.create(
        stage_id=stage_id,
        title=title,
        description=description,
        owner=owner,
        priority=TaskPriority(priority),
        due_date=date.fromisoformat(due_date) if due_date else None,
    )
    db.save_task(task)
    console.print(f"[green]Task created:[/] {task.title} [dim](ID: {task.id[:8]})[/]")


@task_app.command("done")
def task_done(
    task_id: str = typer.Argument(..., help="Task ID"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Completion notes"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Mark a task as done."""
    db = _get_db(db_path)
    task = db.get_task(task_id)
    if not task:
        _abort(f"Task '{task_id}' not found.")

    task.status = TaskStatus.DONE
    task.completed_at = datetime.utcnow()
    if notes:
        task.notes = notes
    db.save_task(task)
    console.print(f"[green]✓[/] Task marked done: [cyan]{task.title}[/]")


@task_app.command("update")
def task_update(
    task_id: str = typer.Argument(..., help="Task ID"),
    status: Optional[str] = typer.Option(None, "--status"),
    owner: Optional[str] = typer.Option(None, "--owner"),
    priority: Optional[str] = typer.Option(None, "--priority"),
    due_date: Optional[str] = typer.Option(None, "--due"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Update a task."""
    db = _get_db(db_path)
    task = db.get_task(task_id)
    if not task:
        _abort(f"Task '{task_id}' not found.")

    if status:
        task.status = TaskStatus(status)
        if status == "done" and not task.completed_at:
            task.completed_at = datetime.utcnow()
    if owner:
        task.owner = owner
    if priority:
        task.priority = TaskPriority(priority)
    if due_date:
        task.due_date = date.fromisoformat(due_date)
    if notes:
        task.notes = notes

    db.save_task(task)
    console.print(f"[green]Updated[/] task [cyan]{task.title}[/].")


# ── Report command ────────────────────────────────────────────────────────────


@app.command("report")
def report(
    id_or_name: Optional[str] = typer.Argument(None, help="Product ID/name for single report"),
    all_products: bool = typer.Option(False, "--all", "-a", help="Report on all products"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Generate a commercialization status report."""
    from .reports import render_pipeline_report, render_product_report

    db = _get_db(db_path)
    if all_products or not id_or_name:
        products = db.list_products()
        render_pipeline_report(console, products)
    else:
        product = _find_product(db, id_or_name)
        render_product_report(console, product)


# ── Render helpers ────────────────────────────────────────────────────────────


def _render_product(product: Product) -> None:
    console.print(f"\n[bold cyan]{product.name}[/]  [dim]{product.id}[/]")
    console.print(f"  Owner: {product.owner}")
    if product.description:
        console.print(f"  Description: {product.description}")
    if product.business_unit:
        console.print(f"  Business Unit: {product.business_unit}")
    if product.target_market:
        console.print(f"  Target Market: {product.target_market}")

    color = _status_color(product.status.value)
    console.print(f"  Status: [{color}]{product.status.value}[/]")
    console.print(f"  Current Stage: [bold]{product.current_stage.display_name}[/]")
    console.print(f"  Overall Progress: {product.overall_progress}%")
    if product.tags:
        console.print(f"  Tags: {', '.join(product.tags)}")
    console.print()

    for stage in product.stages:
        _render_stage_summary(stage)


def _render_stage_summary(stage: Stage) -> None:
    color = _status_color(stage.status.value)
    tasks_done = sum(1 for t in stage.tasks if t.status == TaskStatus.DONE)
    gates_met = sum(1 for g in stage.gate_criteria if g.is_met)

    console.print(
        f"  [bold]{stage.name.display_name}[/]  [{color}]{stage.status.value}[/]"
        f"  Tasks: {tasks_done}/{len(stage.tasks)}  Gate: {gates_met}/{len(stage.gate_criteria)}"
    )
    console.print(f"    Stage ID: [dim]{stage.id}[/]")
    if stage.owner:
        console.print(f"    Owner: {stage.owner}")
    if stage.target_date:
        console.print(f"    Target: {stage.target_date}")
    console.print()


def _render_stage(stage: Stage) -> None:
    color = _status_color(stage.status.value)
    console.print(f"\n[bold cyan]{stage.name.display_name}[/]  [{color}]{stage.status.value}[/]")
    console.print(f"  Stage ID: [dim]{stage.id}[/]")
    console.print(f"  Product ID: [dim]{stage.product_id}[/]")
    if stage.owner:
        console.print(f"  Owner: {stage.owner}")
    if stage.target_date:
        console.print(f"  Target Date: {stage.target_date}")
    if stage.notes:
        console.print(f"  Notes: {stage.notes}")

    console.print(f"\n  Task completion: {stage.task_completion_pct}%")
    console.print(f"  Gate readiness: {stage.gate_completion_pct}%\n")

    if stage.tasks:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Task")
        table.add_column("Priority")
        table.add_column("Status")
        table.add_column("Owner")
        table.add_column("Due")

        for t in stage.tasks:
            s_color = _status_color(t.status.value)
            p_color = _priority_color(t.priority.value)
            table.add_row(
                t.id[:8],
                t.title,
                f"[{p_color}]{t.priority.value}[/]",
                f"[{s_color}]{t.status.value}[/]",
                t.owner or "",
                str(t.due_date) if t.due_date else "",
            )
        console.print("  [bold]Tasks[/]")
        console.print(table)

    if stage.gate_criteria:
        console.print("  [bold]Gate Criteria[/]")
        for g in stage.gate_criteria:
            symbol = "[green]✓[/]" if g.is_met else "[red]✗[/]"
            console.print(f"    {symbol} {g.description}  [dim]{g.id[:8]}[/]")
    console.print()
