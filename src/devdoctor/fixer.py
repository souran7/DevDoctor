"""Fix engine for DevDoctor: safe automatic fixes vs action-required fixes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.prompt import Confirm

from devdoctor.models import Diagnostic, DiagnosticReport, FixAction, ScanContext
from devdoctor.utils.process_utils import free_port, get_port_listener_info


@dataclass
class FixItem:
    """A single diagnostic that has an executable fix."""
    diagnostic: Diagnostic
    action: FixAction

    @property
    def is_safe(self) -> bool:
        return self.action.safe

    @property
    def description(self) -> str:
        return self.action.description or self.diagnostic.fix or "Apply suggested fix"


@dataclass
class FixPlan:
    """A collection of fixes ready for review or execution."""
    items: List[FixItem] = field(default_factory=list)

    @property
    def safe_items(self) -> List[FixItem]:
        return [i for i in self.items if i.is_safe]

    @property
    def action_items(self) -> List[FixItem]:
        return [i for i in self.items if not i.is_safe]

    @property
    def total_count(self) -> int:
        return len(self.items)


@dataclass
class FixResult:
    """Outcome of applying a fix plan."""
    applied: List[FixItem] = field(default_factory=list)
    failed: List[FixItem] = field(default_factory=list)
    skipped: List[FixItem] = field(default_factory=list)


class Fixer:
    """Coordinates deterministic, safe fix application."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def build_plan(self, report: DiagnosticReport) -> FixPlan:
        """Create a FixPlan from report diagnostics that have fix actions."""
        items: List[FixItem] = []
        for d in report.problems:
            if d.fix_action:
                items.append(FixItem(diagnostic=d, action=d.fix_action))
        return FixPlan(items=items)

    def execute_plan(
        self,
        plan: FixPlan,
        context: ScanContext,
        safe_only: bool = False,
        dry_run: bool = False,
        auto_yes: bool = False,
        interactive: bool = True,
    ) -> FixResult:
        """Execute or preview fixes in the plan."""
        result = FixResult()

        if plan.total_count == 0:
            self.console.print("[dim]No automated fixes available for identified problems.[/dim]")
            return result

        candidates = plan.safe_items if safe_only else plan.items

        if not candidates:
            self.console.print("[yellow]No safe automatic fixes found. Remaining fixes require manual confirmation.[/yellow]")
            return result

        self.console.print(f"[bold cyan]Found {len(candidates)} problem(s) with available fixes:[/bold cyan]\n")
        for i, item in enumerate(candidates, start=1):
            badge = "[green][SAFE][/green]" if item.is_safe else "[yellow][ACTION][/yellow]"
            self.console.print(f" {i}. {badge} {item.description}")
            if item.action.command:
                self.console.print(f"    [dim]Command: {item.action.command}[/dim]")

        self.console.print()

        if dry_run:
            self.console.print("[bold yellow][DRY RUN] No changes were made to your machine or project.[/bold yellow]")
            return result

        # Confirm if interactive and not auto_yes and not safe_only
        if interactive and not auto_yes and not safe_only:
            try:
                proceed = Confirm.ask("Apply fixes?", default=True)
                if not proceed:
                    self.console.print("[dim]Aborted by user. No fixes applied.[/dim]")
                    result.skipped.extend(candidates)
                    return result
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[dim]Aborted.[/dim]")
                return result

        # Apply fixes
        self.console.print("\n[bold]Applying fixes...[/bold]\n")
        for item in candidates:
            try:
                success = item.action.execute(context)
                if success:
                    self.console.print(f"[green]✓ Fixed:[/green] {item.description}")
                    result.applied.append(item)
                else:
                    self.console.print(f"[red]❌ Failed:[/red] {item.description}")
                    result.failed.append(item)
            except Exception as e:
                self.console.print(f"[red]❌ Error fixing {item.description}:[/red] {e}")
                result.failed.append(item)

        self.console.print(f"\n[bold green]Completed:[/bold green] {len(result.applied)} applied, {len(result.failed)} failed.")
        return result

    def free_port_interactive(self, port: int, auto_yes: bool = False) -> bool:
        """Safely free an occupied port."""
        info = get_port_listener_info(port)
        if not info or info.pid <= 0:
            self.console.print(f"[green]✓ Port {port} is already free.[/green]")
            return True

        self.console.print(f"[yellow]Port {port} is occupied by {info.process_name} (PID: {info.pid}).[/yellow]")
        if not auto_yes:
            try:
                proceed = Confirm.ask(f"Terminate process {info.process_name} (PID: {info.pid})?", default=False)
                if not proceed:
                    self.console.print("[dim]Action cancelled.[/dim]")
                    return False
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[dim]Cancelled.[/dim]")
                return False

        freed = free_port(port)
        if freed:
            self.console.print(f"[bold green]✓ Port {port} has been freed.[/bold green]")
            return True
        else:
            self.console.print(f"[bold red]❌ Failed to terminate process on port {port}. Run with elevated permissions if required.[/bold red]")
            return False
