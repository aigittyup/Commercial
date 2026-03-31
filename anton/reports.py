"""Reporting module for Anton - pipeline and product status reports."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import Product, ProductStatus, StageName, StageStatus, TaskStatus


_STAGE_ORDER = list(StageName)
_STAGE_ICONS = {
    StageName.IDEATION: "💡",
    StageName.MARKET_RESEARCH: "🔍",
    StageName.BUSINESS_CASE: "📊",
    StageName.PRODUCT_DEVELOPMENT: "⚙️ ",
    StageName.LAUNCH_PREPARATION: "🚀",
    StageName.GO_TO_MARKET: "📣",
    StageName.POST_LAUNCH_REVIEW: "📈",
}


def _progress_bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[cyan]{bar}[/] {pct:5.1f}%"


def _stage_status_icon(status: StageStatus) -> str:
    return {
        StageStatus.NOT_STARTED: "[dim]○[/]",
        StageStatus.IN_PROGRESS: "[cyan]◉[/]",
        StageStatus.COMPLETED: "[green]●[/]",
        StageStatus.BLOCKED: "[red]✕[/]",
        StageStatus.SKIPPED: "[dim]–[/]",
    }.get(status, "○")


def render_pipeline_report(console: Console, products: list[Product]) -> None:
    """Render a high-level pipeline overview for all products."""
    if not products:
        console.print("[dim]No products in the pipeline.[/]")
        return

    console.print()
    console.print(Panel("[bold]Anton Commercialization Pipeline[/]", expand=False))
    console.print()

    # Summary stats
    by_status = {s: 0 for s in ProductStatus}
    for p in products:
        by_status[p.status] += 1

    stats_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    stats_table.add_column()
    stats_table.add_column(justify="right")
    stats_table.add_row("[bold]Total Products[/]", str(len(products)))
    stats_table.add_row("[green]Active[/]", str(by_status[ProductStatus.ACTIVE]))
    stats_table.add_row("[blue]Launched[/]", str(by_status[ProductStatus.LAUNCHED]))
    stats_table.add_row("[yellow]On Hold[/]", str(by_status[ProductStatus.ON_HOLD]))
    stats_table.add_row("[red]Cancelled[/]", str(by_status[ProductStatus.CANCELLED]))
    console.print(stats_table)
    console.print()

    # Pipeline table
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Product", min_width=18)
    table.add_column("Owner")
    table.add_column("Stage")
    table.add_column("Progress", min_width=28)
    table.add_column("Open Tasks", justify="right")
    table.add_column("Blocked", justify="right")

    for p in products:
        if p.status == ProductStatus.CANCELLED:
            continue
        open_tasks = sum(
            1
            for s in p.stages
            for t in s.tasks
            if t.status in (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)
        )
        blocked_tasks = sum(
            1 for s in p.stages for t in s.tasks if t.status == TaskStatus.BLOCKED
        )
        table.add_row(
            f"[bold]{p.name}[/]",
            p.owner,
            p.current_stage.display_name,
            _progress_bar(p.overall_progress),
            str(open_tasks),
            f"[red]{blocked_tasks}[/]" if blocked_tasks else "0",
        )

    console.print(table)
    console.print()


def render_product_report(console: Console, product: Product) -> None:
    """Render a detailed commercialization status report for a single product."""
    console.print()
    title = Text()
    title.append("Product Report: ", style="bold")
    title.append(product.name, style="bold cyan")
    console.print(Panel(title, expand=False))
    console.print()

    # Header info
    meta = Table(box=None, show_header=False, padding=(0, 2))
    meta.add_column(style="dim")
    meta.add_column()
    meta.add_row("Owner", product.owner)
    if product.business_unit:
        meta.add_row("Business Unit", product.business_unit)
    if product.target_market:
        meta.add_row("Target Market", product.target_market)
    meta.add_row("Status", product.status.value)
    meta.add_row("Created", product.created_at.strftime("%Y-%m-%d"))
    if product.launched_at:
        meta.add_row("Launched", product.launched_at.strftime("%Y-%m-%d"))
    if product.tags:
        meta.add_row("Tags", ", ".join(product.tags))
    if product.description:
        meta.add_row("Description", product.description)
    console.print(meta)
    console.print()

    # Overall progress
    console.print(f"  Overall Progress  {_progress_bar(product.overall_progress, 30)}")
    console.print()

    # Stage pipeline visualization
    console.print("[bold]Commercialization Pipeline[/]\n")
    for stage_name in _STAGE_ORDER:
        stage = product.get_stage(stage_name)
        icon = _STAGE_ICONS.get(stage_name, "  ")
        is_current = stage_name == product.current_stage

        if not stage:
            console.print(f"  {icon} [dim]{stage_name.display_name}[/]")
            continue

        status_icon = _stage_status_icon(stage.status)
        name_style = "bold" if is_current else ""
        marker = " ◄ CURRENT" if is_current else ""

        tasks_done = sum(1 for t in stage.tasks if t.status == TaskStatus.DONE)
        gates_met = sum(1 for g in stage.gate_criteria if g.is_met)

        console.print(
            f"  {status_icon} {icon} [{name_style}]{stage_name.display_name}[/]{marker}"
            f"  [dim]Tasks {tasks_done}/{len(stage.tasks)} · Gate {gates_met}/{len(stage.gate_criteria)}[/]"
        )
        if stage.target_date:
            console.print(f"       Target: {stage.target_date}")

    console.print()

    # Current stage deep-dive
    current_stage = product.get_stage(product.current_stage)
    if not current_stage:
        return

    console.print(
        f"[bold]Current Stage: {product.current_stage.display_name}[/] "
        f"[dim](ID: {current_stage.id})[/]\n"
    )

    # Open / blocked tasks
    open_tasks = [
        t
        for t in current_stage.tasks
        if t.status in (TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)
    ]
    if open_tasks:
        task_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        task_table.add_column("Priority", width=10)
        task_table.add_column("Task")
        task_table.add_column("Owner")
        task_table.add_column("Status")

        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        open_tasks.sort(key=lambda t: priority_order.get(t.priority.value, 9))

        for t in open_tasks:
            p_color = {
                "critical": "bold red",
                "high": "yellow",
                "medium": "white",
                "low": "dim",
            }.get(t.priority.value, "white")
            s_color = {"blocked": "red", "in_progress": "cyan", "open": "dim"}.get(
                t.status.value, "white"
            )
            task_table.add_row(
                f"[{p_color}]{t.priority.value}[/]",
                t.title,
                t.owner or "",
                f"[{s_color}]{t.status.value}[/]",
            )
        console.print("  [bold]Open Tasks[/]")
        console.print(task_table)
    else:
        console.print("  [green]All tasks in current stage are complete.[/]\n")

    # Gate criteria
    console.print("  [bold]Gate Criteria[/]")
    for g in current_stage.gate_criteria:
        symbol = "[green]✓[/]" if g.is_met else "[red]✗[/]"
        by = f" [dim](verified by {g.verified_by})[/]" if g.verified_by else ""
        console.print(f"    {symbol} {g.description}{by}")

    gate_ready = current_stage.is_gate_ready
    console.print()
    if gate_ready:
        console.print(
            "  [bold green]✓ Gate criteria fully met — ready to advance to next stage.[/]"
        )
    else:
        unmet = sum(1 for g in current_stage.gate_criteria if not g.is_met)
        console.print(
            f"  [yellow]⚠ {unmet} gate criterion/criteria not yet met.[/]"
        )
    console.print()
