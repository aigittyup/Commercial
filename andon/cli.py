"""Andon CLI - Commercialization Alert and Escalation System."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .db import AndonDB
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

app = typer.Typer(
    name="andon",
    help=(
        "Andon — Real-time alert and escalation system for new product commercialization.\n\n"
        "Pull the cord when you hit a blocker. Acknowledge it. Resolve it. Learn from it."
    ),
    no_args_is_help=True,
)
product_app = typer.Typer(help="Manage products in the commercialization pipeline.")
signal_app = typer.Typer(help="Raise, acknowledge, resolve, and escalate Andon signals.")

app.add_typer(product_app, name="product")
app.add_typer(signal_app, name="signal")

console = Console()
err_console = Console(stderr=True)

_DB_PATH_OPT = typer.Option(None, "--db", help="Path to Andon database file.")


def _get_db(db_path: Optional[Path]) -> AndonDB:
    return AndonDB(db_path) if db_path else AndonDB()


def _abort(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/] {msg}")
    raise typer.Exit(1)


def _find_product(db: AndonDB, id_or_name: str) -> Product:
    product = db.get_product(id_or_name)
    if not product:
        matches = [p for p in db.list_products() if id_or_name.lower() in p.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            _abort(f"'{id_or_name}' matches multiple products. Use the full product ID.")
        _abort(f"Product '{id_or_name}' not found.")
    return product  # type: ignore[return-value]


def _find_signal(db: AndonDB, signal_id: str) -> AndonSignal:
    if len(signal_id) < 36:
        all_signals = db.list_signals()
        matches = [s for s in all_signals if s.id.startswith(signal_id)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            _abort(f"ID prefix '{signal_id}' is ambiguous. Use more characters.")
        _abort(f"Signal '{signal_id}' not found.")
    signal = db.get_signal(signal_id)
    if not signal:
        _abort(f"Signal '{signal_id}' not found.")
    return signal  # type: ignore[return-value]


# ── Product commands ──────────────────────────────────────────────────────────


@product_app.command("new")
def product_new(
    name: str = typer.Argument(..., help="Product name"),
    owner: str = typer.Option(..., "--owner", "-o", help="Product owner / PM"),
    business_unit: Optional[str] = typer.Option(None, "--bu", help="Business unit"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Register a new product in the Andon commercialization pipeline."""
    db = _get_db(db_path)
    product = Product.create(name=name, owner=owner, business_unit=business_unit)
    db.save_product(product)

    for stage_name in StageName:
        stage = Stage.create(product_id=product.id, name=stage_name, owner=owner)
        if stage_name == StageName.IDEATION:
            stage.status = StageStatus.IN_PROGRESS
        db.save_stage(stage)

    console.print(
        f"\n[bold green]Product registered:[/] [cyan]{product.name}[/] "
        f"[dim](ID: {product.id[:8]})[/]\n"
        f"  Pipeline initialised through 7 stages.\n"
        f"  Pull the cord with: [bold]andon signal raise {product.id[:8]} "
        f"--title \"...\" --by <name>[/]\n"
    )


@product_app.command("list")
def product_list(db_path: Optional[Path] = _DB_PATH_OPT):
    """List all products with their Andon status."""
    from .board import render_product_list
    db = _get_db(db_path)
    render_product_list(console, db.list_products())


@product_app.command("advance")
def product_advance(
    id_or_name: str = typer.Argument(..., help="Product ID or name"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Advance a product to the next pipeline stage."""
    db = _get_db(db_path)
    product = _find_product(db, id_or_name)

    open_sigs = product.open_signals
    if open_sigs:
        console.print(
            f"[bold yellow]Warning:[/] {len(open_sigs)} open signal(s) on this product:"
        )
        for s in open_sigs:
            console.print(
                f"  [{_sev_color(s.severity.value)}]{s.severity.value.upper()}[/] {s.title}"
            )
        if not typer.confirm("\nAdvance anyway?"):
            raise typer.Exit(0)

    stage_order = list(StageName)
    idx = stage_order.index(product.current_stage)
    if idx >= len(stage_order) - 1:
        _abort("Product is already at the final stage.")

    for stage in product.stages:
        if stage.name == product.current_stage:
            stage.status = StageStatus.COMPLETED
            db.save_stage(stage)
            break

    next_stage = stage_order[idx + 1]
    product.current_stage = next_stage

    for stage in product.stages:
        if stage.name == next_stage:
            stage.status = StageStatus.IN_PROGRESS
            db.save_stage(stage)
            break

    db.save_product(product)
    console.print(
        f"[green]Advanced[/] [cyan]{product.name}[/] → [bold]{next_stage.display_name}[/]"
    )


# ── Signal commands ───────────────────────────────────────────────────────────


@signal_app.command("raise")
def signal_raise(
    product: str = typer.Argument(..., help="Product ID or name"),
    title: str = typer.Option(..., "--title", "-t", help="Short description of the issue"),
    raised_by: str = typer.Option(..., "--by", "-b", help="Your name"),
    severity: str = typer.Option(
        "warning", "--severity", "-s", help="info | warning | critical | stop"
    ),
    category: str = typer.Option(
        "blocker",
        "--category",
        "-c",
        help="quality | blocker | resource | decision | risk | compliance",
    ),
    description: str = typer.Option("", "--description", "-d", help="Full description"),
    stage: Optional[str] = typer.Option(None, "--stage", help="Stage name (defaults to current)"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Pull the Andon cord — raise a signal on a product."""
    db = _get_db(db_path)
    p = _find_product(db, product)

    stage_name = StageName(stage) if stage else p.current_stage
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    signal = AndonSignal.create(
        product_id=p.id,
        stage_name=stage_name,
        title=title,
        description=description,
        raised_by=raised_by,
        severity=SignalSeverity(severity),
        category=SignalCategory(category),
        tags=tag_list,
    )
    db.save_signal(signal)

    if signal.severity in (SignalSeverity.CRITICAL, SignalSeverity.STOP):
        for s in p.stages:
            if s.name == stage_name and s.status == StageStatus.IN_PROGRESS:
                s.status = StageStatus.BLOCKED
                db.save_stage(s)
                break

    sev_color = _sev_color(severity)
    console.print(
        f"\n[{sev_color}]ANDON SIGNAL RAISED[/]\n"
        f"  Signal ID : [dim]{signal.id[:8]}[/]\n"
        f"  Product   : {p.name}\n"
        f"  Stage     : {stage_name.display_name}\n"
        f"  Severity  : [{sev_color}]{severity.upper()}[/]\n"
        f"  Category  : {category}\n"
        f"  Title     : {title}\n"
        f"\n  Acknowledge with: [bold]andon signal ack {signal.id[:8]} --by <name>[/]\n"
    )


@signal_app.command("ack")
def signal_ack(
    signal_id: str = typer.Argument(..., help="Signal ID (or prefix)"),
    by: str = typer.Option(..., "--by", "-b", help="Your name"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Acknowledge an open Andon signal — take ownership of the issue."""
    db = _get_db(db_path)
    signal = _find_signal(db, signal_id)

    if signal.status == SignalStatus.RESOLVED:
        _abort("Signal is already resolved.")

    signal.status = SignalStatus.ACKNOWLEDGED
    signal.acknowledged_by = by
    signal.acknowledged_at = datetime.utcnow()
    db.save_signal(signal)

    console.print(
        f"[cyan]Acknowledged[/] signal [dim]{signal.id[:8]}[/]\n"
        f"  '{signal.title}'\n"
        f"  Owned by: {by}\n"
        f"\n  Resolve with: [bold]andon signal resolve {signal.id[:8]} --by {by} "
        f'--root-cause "..."[/]\n'
    )


@signal_app.command("resolve")
def signal_resolve(
    signal_id: str = typer.Argument(..., help="Signal ID (or prefix)"),
    by: str = typer.Option(..., "--by", "-b", help="Your name"),
    root_cause: str = typer.Option(..., "--root-cause", "-r", help="Root cause of the issue"),
    corrective_action: str = typer.Option(
        "", "--action", "-a", help="What was done to fix it"
    ),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """
    Resolve an Andon signal with root cause and corrective action documented.

    Root cause data feeds continuous improvement (Kaizen / 5-Why analysis).
    """
    db = _get_db(db_path)
    signal = _find_signal(db, signal_id)

    if signal.status == SignalStatus.RESOLVED:
        _abort("Signal is already resolved.")

    signal.status = SignalStatus.RESOLVED
    signal.resolved_by = by
    signal.resolved_at = datetime.utcnow()
    signal.root_cause = root_cause
    signal.corrective_action = corrective_action or None
    db.save_signal(signal)

    # Restore blocked stage if no other open signals remain for that stage
    product = db.get_product(signal.product_id)
    if product:
        remaining_open = [
            s
            for s in product.signals
            if s.is_open and s.stage_name == signal.stage_name and s.id != signal.id
        ]
        if not remaining_open:
            for stage in product.stages:
                if stage.name == signal.stage_name and stage.status == StageStatus.BLOCKED:
                    stage.status = StageStatus.IN_PROGRESS
                    db.save_stage(stage)
                    break

    console.print(
        f"[green]Resolved[/] signal [dim]{signal.id[:8]}[/]\n"
        f"  Title     : {signal.title}\n"
        f"  Root cause: {root_cause}\n"
        f"  Age       : {signal.age_hours}h\n"
    )
    if corrective_action:
        console.print(f"  Corrective action: {corrective_action}\n")


@signal_app.command("escalate")
def signal_escalate(
    signal_id: str = typer.Argument(..., help="Signal ID (or prefix)"),
    by: str = typer.Option(..., "--by", "-b", help="Your name"),
    reason: str = typer.Option(..., "--reason", "-r", help="Why is this being escalated?"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Escalate a signal to the next level (Team → Manager → Director → Executive)."""
    db = _get_db(db_path)
    signal = _find_signal(db, signal_id)

    if signal.status == SignalStatus.RESOLVED:
        _abort("Cannot escalate a resolved signal.")

    levels = list(EscalationLevel)
    current_idx = levels.index(signal.escalation_level)
    if current_idx >= len(levels) - 1:
        _abort("Signal is already at the highest escalation level (Executive).")

    from_level = signal.escalation_level
    to_level = levels[current_idx + 1]

    event = EscalationEvent.create(
        signal_id=signal.id,
        from_level=from_level,
        to_level=to_level,
        escalated_by=by,
        reason=reason,
    )
    db.save_escalation(event)

    signal.escalation_level = to_level
    signal.status = SignalStatus.ESCALATED
    db.save_signal(signal)

    console.print(
        f"[bold yellow]Escalated[/] signal [dim]{signal.id[:8]}[/]\n"
        f"  '{signal.title}'\n"
        f"  {from_level.name} → [bold]{to_level.name}[/]\n"
        f"  Reason: {reason}\n"
    )


@signal_app.command("list")
def signal_list(
    product: Optional[str] = typer.Option(None, "--product", "-p"),
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="open | acknowledged | resolved | escalated"
    ),
    severity: Optional[str] = typer.Option(None, "--severity"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """List Andon signals with optional filters."""
    from .board import render_signal_table
    db = _get_db(db_path)

    product_id = None
    if product:
        p = _find_product(db, product)
        product_id = p.id

    signals = db.list_signals(
        product_id=product_id,
        status=SignalStatus(status) if status else None,
        severity=SignalSeverity(severity) if severity else None,
    )
    render_signal_table(console, signals)


@signal_app.command("show")
def signal_show(
    signal_id: str = typer.Argument(..., help="Signal ID (or prefix)"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Show full details for a signal including escalation history."""
    from .board import render_signal_detail
    db = _get_db(db_path)
    signal = _find_signal(db, signal_id)
    product = db.get_product(signal.product_id)
    render_signal_detail(console, signal, product)


# ── Board command ─────────────────────────────────────────────────────────────


@app.command("board")
def board(db_path: Optional[Path] = _DB_PATH_OPT):
    """Display the Andon board — colour-coded status of all products in the pipeline."""
    from .board import render_andon_board
    db = _get_db(db_path)
    render_andon_board(console, db.list_products())


# ── Report command ────────────────────────────────────────────────────────────


@app.command("report")
def report(
    product: Optional[str] = typer.Argument(None, help="Product ID/name (omit for all)"),
    db_path: Optional[Path] = _DB_PATH_OPT,
):
    """Generate a Kaizen report from resolved signal root causes."""
    from .board import render_kaizen_report, render_product_report
    db = _get_db(db_path)
    if product:
        p = _find_product(db, product)
        render_product_report(console, p)
    else:
        render_kaizen_report(console, db.list_products(), db.list_signals())


# ── Helpers ───────────────────────────────────────────────────────────────────


def _sev_color(severity: str) -> str:
    return {
        "info": "blue",
        "warning": "yellow",
        "critical": "bold red",
        "stop": "bold red reverse",
    }.get(severity, "white")
