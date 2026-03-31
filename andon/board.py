"""Andon board and reporting displays."""

from __future__ import annotations

from collections import Counter
from typing import Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import (
    AndonSignal,
    EscalationLevel,
    Product,
    SignalCategory,
    SignalSeverity,
    SignalStatus,
    StageName,
    StageStatus,
)

_STAGE_ICONS = {
    StageName.IDEATION: "💡",
    StageName.MARKET_RESEARCH: "🔍",
    StageName.BUSINESS_CASE: "📊",
    StageName.PRODUCT_DEVELOPMENT: "⚙️ ",
    StageName.LAUNCH_PREPARATION: "🚀",
    StageName.GO_TO_MARKET: "📣",
    StageName.POST_LAUNCH_REVIEW: "📈",
}

_ANDON_LIGHT = {
    "green": "[bold green]●  GREEN [/]",
    "blue": "[bold blue]●  BLUE  [/]",
    "yellow": "[bold yellow]●  YELLOW[/]",
    "red": "[bold red]●  RED   [/]",
    "stop": "[bold red reverse]⚡  STOP   [/]",
}

_ANDON_PANEL_STYLE = {
    "green": "green",
    "blue": "blue",
    "yellow": "yellow",
    "red": "red",
    "stop": "red",
}


def _sev_color(severity: str) -> str:
    return {
        "info": "blue",
        "warning": "yellow",
        "critical": "bold red",
        "stop": "bold red reverse",
    }.get(severity, "white")


def _status_color(status: str) -> str:
    return {
        "open": "yellow",
        "acknowledged": "cyan",
        "resolved": "green",
        "escalated": "bold red",
    }.get(status, "white")


def _stage_status_icon(status: StageStatus) -> str:
    return {
        StageStatus.NOT_STARTED: "[dim]○[/]",
        StageStatus.IN_PROGRESS: "[cyan]◉[/]",
        StageStatus.COMPLETED: "[green]●[/]",
        StageStatus.BLOCKED: "[bold red]✕[/]",
    }.get(status, "○")


# ── Andon Board ───────────────────────────────────────────────────────────────


def render_andon_board(console: Console, products: list[Product]) -> None:
    """
    The Andon board — one panel per product, colour coded by alert severity.

    Green  = all clear
    Blue   = informational signal(s) only
    Yellow = warning signal(s) present
    Red    = critical signal(s) — work at risk
    Stop   = STOP signal — full stoppage, escalate immediately
    """
    console.print()
    console.print(Panel("[bold]ANDON BOARD[/] — Commercialization Pipeline", expand=False))
    console.print()

    if not products:
        console.print("[dim]No products registered.[/]\n")
        return

    for product in products:
        color = product.andon_color
        light = _ANDON_LIGHT[color]
        open_sigs = product.open_signals
        style = _ANDON_PANEL_STYLE[color]

        # Build stage pipeline row
        pipeline = ""
        for stage in product.stages:
            icon = _STAGE_ICONS.get(stage.name, "  ")
            status_icon = _stage_status_icon(stage.status)
            marker = "[bold]" if stage.name == product.current_stage else "[dim]"
            end = "[/]" if stage.name == product.current_stage else "[/]"
            pipeline += f" {status_icon}{marker}{icon}[/] "

        # Build open signal summary
        sig_lines = ""
        for sig in open_sigs[:3]:  # show top 3
            sc = _sev_color(sig.severity.value)
            esc = f" [dim](Escalated: {sig.escalation_level.name})[/]" if sig.status == SignalStatus.ESCALATED else ""
            sig_lines += f"\n  [{sc}]{sig.severity.value.upper()}[/] [{sig.category.value}] {sig.title}{esc}"
        if len(open_sigs) > 3:
            sig_lines += f"\n  [dim]... and {len(open_sigs) - 3} more[/]"

        body = (
            f"{light}  {product.name}  [dim]{product.id[:8]}[/]\n"
            f"  Owner: {product.owner}"
            + (f"  |  BU: {product.business_unit}" if product.business_unit else "")
            + f"\n  Stage: [bold]{product.current_stage.display_name}[/]\n"
            + f"  Pipeline:{pipeline}\n"
            + (f"  Open signals: {len(open_sigs)}{sig_lines}" if open_sigs else "  [dim]No open signals[/]")
        )

        console.print(Panel(body, border_style=style, expand=True))

    console.print()


# ── Product list ──────────────────────────────────────────────────────────────


def render_product_list(console: Console, products: list[Product]) -> None:
    if not products:
        console.print("[dim]No products registered.[/]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Product", min_width=18)
    table.add_column("Owner")
    table.add_column("Stage")
    table.add_column("Andon", justify="center")
    table.add_column("Open", justify="right")
    table.add_column("Escalated", justify="right")

    for p in products:
        color = p.andon_color
        light_str = {
            "green": "[green]●[/]",
            "blue": "[blue]●[/]",
            "yellow": "[yellow]●[/]",
            "red": "[red]●[/]",
            "stop": "[bold red reverse]⚡[/]",
        }[color]
        open_count = len(p.open_signals)
        esc_count = sum(1 for s in p.open_signals if s.status == SignalStatus.ESCALATED)
        table.add_row(
            p.id[:8],
            p.name,
            p.owner,
            p.current_stage.display_name,
            light_str,
            str(open_count) if open_count else "[dim]0[/]",
            f"[bold red]{esc_count}[/]" if esc_count else "[dim]0[/]",
        )

    console.print(f"\n[bold]Products[/] ({len(products)} total)\n")
    console.print(table)
    console.print()


# ── Signal table ──────────────────────────────────────────────────────────────


def render_signal_table(console: Console, signals: list[AndonSignal]) -> None:
    if not signals:
        console.print("[dim]No signals found.[/]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Severity")
    table.add_column("Category")
    table.add_column("Title", min_width=25)
    table.add_column("Status")
    table.add_column("Stage")
    table.add_column("Raised by")
    table.add_column("Age (h)", justify="right")
    table.add_column("Esc. Level")

    for sig in signals:
        sc = _sev_color(sig.severity.value)
        stc = _status_color(sig.status.value)
        table.add_row(
            sig.id[:8],
            f"[{sc}]{sig.severity.value}[/]",
            sig.category.value,
            sig.title,
            f"[{stc}]{sig.status.value}[/]",
            sig.stage_name.display_name,
            sig.raised_by,
            str(sig.age_hours),
            sig.escalation_level.name,
        )

    console.print(f"\n[bold]Signals[/] ({len(signals)} total)\n")
    console.print(table)
    console.print()


# ── Signal detail ─────────────────────────────────────────────────────────────


def render_signal_detail(
    console: Console, signal: AndonSignal, product: Optional[Product]
) -> None:
    sc = _sev_color(signal.severity.value)
    stc = _status_color(signal.status.value)

    console.print()
    console.print(
        Panel(
            f"[{sc}]{signal.severity.value.upper()}[/]  [{stc}]{signal.status.value}[/]  "
            f"[bold]{signal.title}[/]",
            expand=False,
        )
    )
    console.print()

    meta = Table(box=None, show_header=False, padding=(0, 2))
    meta.add_column(style="dim", width=20)
    meta.add_column()
    meta.add_row("Signal ID", signal.id)
    if product:
        meta.add_row("Product", f"{product.name} ({signal.product_id[:8]})")
    meta.add_row("Stage", signal.stage_name.display_name)
    meta.add_row("Category", signal.category.value)
    meta.add_row("Raised by", signal.raised_by)
    meta.add_row("Raised at", signal.raised_at.strftime("%Y-%m-%d %H:%M UTC"))
    meta.add_row("Age", f"{signal.age_hours}h")
    meta.add_row("Escalation level", signal.escalation_level.name)
    if signal.description:
        meta.add_row("Description", signal.description)
    if signal.acknowledged_by:
        meta.add_row(
            "Acknowledged by",
            f"{signal.acknowledged_by} at "
            + (signal.acknowledged_at.strftime("%Y-%m-%d %H:%M") if signal.acknowledged_at else ""),
        )
    if signal.resolved_by:
        meta.add_row(
            "Resolved by",
            f"{signal.resolved_by} at "
            + (signal.resolved_at.strftime("%Y-%m-%d %H:%M") if signal.resolved_at else ""),
        )
    if signal.root_cause:
        meta.add_row("Root cause", signal.root_cause)
    if signal.corrective_action:
        meta.add_row("Corrective action", signal.corrective_action)
    if signal.tags:
        meta.add_row("Tags", ", ".join(signal.tags))

    console.print(meta)

    if signal.escalation_history:
        console.print("\n  [bold]Escalation History[/]")
        for ev in signal.escalation_history:
            console.print(
                f"  {ev.escalated_at.strftime('%Y-%m-%d %H:%M')}  "
                f"{ev.from_level.name} → [bold]{ev.to_level.name}[/]  "
                f"by {ev.escalated_by}  —  {ev.reason}"
            )
    console.print()


# ── Product report ────────────────────────────────────────────────────────────


def render_product_report(console: Console, product: Product) -> None:
    """Per-product Andon status report with full signal history."""
    color = product.andon_color
    light = _ANDON_LIGHT[color]

    console.print()
    console.print(
        Panel(f"[bold]Andon Report:[/] [cyan]{product.name}[/]", expand=False)
    )
    console.print(f"\n  {light}  Owner: {product.owner}")
    if product.business_unit:
        console.print(f"  Business Unit: {product.business_unit}")
    console.print(f"  Current Stage: [bold]{product.current_stage.display_name}[/]\n")

    # Pipeline
    console.print("  [bold]Pipeline Status[/]")
    for stage in product.stages:
        icon = _STAGE_ICONS.get(stage.name, "  ")
        status_icon = _stage_status_icon(stage.status)
        marker = " ◄ CURRENT" if stage.name == product.current_stage else ""
        blocked = " [bold red][BLOCKED][/]" if stage.status == StageStatus.BLOCKED else ""
        console.print(f"    {status_icon} {icon} {stage.name.display_name}{marker}{blocked}")
    console.print()

    # Open signals
    open_sigs = product.open_signals
    if open_sigs:
        console.print(f"  [bold]Open Signals ({len(open_sigs)})[/]")
        render_signal_table(console, open_sigs)
    else:
        console.print("  [green]No open signals — all clear.[/]\n")

    # Signal history
    resolved = [s for s in product.signals if s.status == SignalStatus.RESOLVED]
    if resolved:
        console.print(f"  [bold]Resolved Signals ({len(resolved)})[/]")
        for sig in resolved:
            console.print(
                f"    [green]✓[/] {sig.title}  [dim]({sig.age_hours}h · "
                f"root cause: {sig.root_cause or 'not recorded'})[/]"
            )
    console.print()


# ── Kaizen report ─────────────────────────────────────────────────────────────


def render_kaizen_report(
    console: Console, products: list[Product], all_signals: list[AndonSignal]
) -> None:
    """
    Continuous improvement (Kaizen) report — aggregate patterns from resolved signals.

    Identifies the most frequent root cause categories and stages to guide
    process improvement efforts.
    """
    console.print()
    console.print(Panel("[bold]Kaizen Continuous Improvement Report[/]", expand=False))
    console.print()

    total = len(all_signals)
    open_count = sum(1 for s in all_signals if s.is_open)
    resolved_count = sum(1 for s in all_signals if s.status == SignalStatus.RESOLVED)
    escalated_count = sum(
        1 for s in all_signals if s.status == SignalStatus.ESCALATED
    )

    # Summary
    summary = Table(box=None, show_header=False, padding=(0, 2))
    summary.add_column(style="dim", width=25)
    summary.add_column()
    summary.add_row("Total signals raised", str(total))
    summary.add_row("Currently open", str(open_count))
    summary.add_row("Resolved", str(resolved_count))
    summary.add_row("Escalated", str(escalated_count))
    if total:
        resolution_rate = round(resolved_count / total * 100, 1)
        summary.add_row("Resolution rate", f"{resolution_rate}%")
    console.print(summary)
    console.print()

    if not all_signals:
        console.print("[dim]No signals recorded yet.[/]\n")
        return

    # Signals by category
    cat_counts = Counter(s.category.value for s in all_signals)
    console.print("[bold]Signals by Category[/]")
    cat_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    cat_table.add_column("Category")
    cat_table.add_column("Count", justify="right")
    cat_table.add_column("% of Total", justify="right")
    for cat, count in cat_counts.most_common():
        pct = round(count / total * 100, 1)
        cat_table.add_row(cat, str(count), f"{pct}%")
    console.print(cat_table)
    console.print()

    # Signals by stage
    stage_counts = Counter(s.stage_name.display_name for s in all_signals)
    console.print("[bold]Signals by Pipeline Stage[/]")
    stage_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    stage_table.add_column("Stage")
    stage_table.add_column("Count", justify="right")
    stage_table.add_column("% of Total", justify="right")
    for stage, count in stage_counts.most_common():
        pct = round(count / total * 100, 1)
        stage_table.add_row(stage, str(count), f"{pct}%")
    console.print(stage_table)
    console.print()

    # Mean time to resolve (open signals excluded)
    resolved_signals = [s for s in all_signals if s.status == SignalStatus.RESOLVED]
    if resolved_signals:
        avg_hours = round(sum(s.age_hours for s in resolved_signals) / len(resolved_signals), 1)
        console.print(f"[bold]Mean Time to Resolve:[/] {avg_hours}h\n")

    # Top recurring root causes
    root_causes = [
        s.root_cause for s in resolved_signals if s.root_cause
    ]
    if root_causes:
        console.print("[bold]Documented Root Causes[/]")
        for i, rc in enumerate(root_causes, 1):
            console.print(f"  {i}. {rc}")
    console.print()
