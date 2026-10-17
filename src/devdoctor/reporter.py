"""DevDoctor output reporter: renders deterministic CLI views, verbose diagnostics, and JSON."""

from __future__ import annotations

import json
import sys
from typing import Optional

from rich.console import Console

# Ensure UTF-8 output on Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configure Console with legacy_windows=False to prevent charmap encoding errors
console = Console(legacy_windows=False)

# Unicode characters with safe ASCII fallbacks if required
def can_encode(char: str) -> bool:
    try:
        char.encode(sys.stdout.encoding or "utf-8")
        return True
    except Exception:
        return False

SYM_OK = "✓" if can_encode("✓") else "[OK]"
SYM_WARN = "⚠" if can_encode("⚠") else "[!]"
SYM_ERR = "❌" if can_encode("❌") else "[X]"
SYM_DIV = "────────────────────────────" if can_encode("─") else "----------------------------"


class Reporter:
    """Renders DiagnosticReports into terminal, verbose, JSON, or Markdown formats."""

    def __init__(self, console_instance: Optional[Console] = None):
        self.console = console_instance or console

    def render_terminal(self, report: DiagnosticReport, verbose: bool = False) -> None:
        """Render the default or verbose DevDoctor scan output to the terminal."""
        if verbose:
            self._render_verbose(report)
            return

        # Header
        self.console.print("[bold cyan]DevDoctor 0.1.0[/bold cyan]")
        if report.project_info and report.project_info.summary_stack:
            self.console.print(f"[dim]Project: {report.project_info.summary_stack}[/dim]")
        self.console.print(f"{SYM_DIV}\n")

        # 1. Passed checks (compact green checkmarks)
        if report.passed:
            for diag in report.passed:
                self.console.print(f"[green]{SYM_OK}[/green] {diag.title}")
            self.console.print()

        # 2. Problems (Warnings and Errors)
        if report.problems:
            for diag in report.problems:
                sym = f"[red]{SYM_ERR}[/red]" if diag.is_error else f"[yellow]{SYM_WARN}[/yellow]"
                self.console.print(f"{sym} [bold]{diag.title}[/bold]")
                if diag.message:
                    self.console.print(f"   {diag.message}\n")

                if diag.evidence:
                    self.console.print(f"   {diag.evidence}\n")

                if diag.fix:
                    self.console.print("   Fix:")
                    for line in diag.fix.splitlines():
                        self.console.print(f"     {line}")
                    self.console.print()

        # 3. Score
        score = report.score
        if score >= 90:
            score_color = "green"
        elif score >= 70:
            score_color = "yellow"
        else:
            score_color = "red"

        self.console.print(f"[bold {score_color}]Score: {score}/100[/bold {score_color}]\n")

        # 4. Summary
        total_p = report.total_problems
        if total_p == 0:
            self.console.print(f"[bold green]{SYM_OK} All checks passed! Machine and project are healthy.[/bold green]")
        else:
            problem_word = "problem" if total_p == 1 else "problems"
            color = "red" if report.errors else "yellow"
            self.console.print(f"[{color}]{total_p} {problem_word} found.[/{color}]")

    def _render_verbose(self, report: DiagnosticReport) -> None:
        """Render full diagnostic detail with WHY, EVIDENCE, SAFE FIX, COMMAND, and Confidence."""
        self.console.print("[bold cyan]DevDoctor 0.1.0 (Detailed Diagnostic Report)[/bold cyan]")
        self.console.print(f"{SYM_DIV * 2}\n")

        if report.passed:
            self.console.print("[bold green]PASSED CHECKS:[/bold green]")
            for diag in report.passed:
                self.console.print(f"  [green]{SYM_OK}[/green] {diag.title}: {diag.message}")
            self.console.print()

        if report.problems:
            self.console.print("[bold red]IDENTIFIED PROBLEMS & DIAGNOSTICS:[/bold red]\n")
            for diag in report.problems:
                sym = SYM_ERR if diag.is_error else SYM_WARN
                self.console.print(f"{sym} [bold underline]{diag.title}[/bold underline]\n")

                if diag.message:
                    self.console.print(f"[bold]PROBLEM:[/bold]\n{diag.message}\n")

                if diag.why:
                    self.console.print(f"[bold]WHY:[/bold]\n{diag.why}\n")

                if diag.evidence:
                    self.console.print(f"[bold]EVIDENCE:[/bold]\n{diag.evidence}\n")

                if diag.fix:
                    self.console.print(f"[bold]SAFE FIX:[/bold]\n{diag.fix}\n")

                if diag.command:
                    self.console.print(f"[bold]COMMAND:[/bold]\n{diag.command}\n")

                conf = diag.confidence.value if hasattr(diag.confidence, "value") else str(diag.confidence)
                self.console.print(f"Confidence: [cyan]{conf}[/cyan]\n")
                self.console.print(f"{SYM_DIV * 2}\n")

        # Score & Summary
        score = report.score
        score_color = "green" if score >= 90 else ("yellow" if score >= 70 else "red")
        self.console.print(f"[bold {score_color}]Health Score: {score}/100[/bold {score_color}] ({report.total_problems} problems found)")

    def render_json(self, report: DiagnosticReport) -> str:
        """Return JSON representation of the diagnostic report."""
        return json.dumps(report.to_dict(), indent=2)

    def render_markdown(self, report: DiagnosticReport) -> str:
        """Render a GitHub-flavored Markdown diagnostic report."""
        lines = [
            f"# DevDoctor Diagnostic Report",
            f"",
            f"- **Target**: `{report.project_path}`",
            f"- **Timestamp**: `{report.timestamp.isoformat()}`",
            f"- **Health Score**: **{report.score}/100**",
            f"- **Problems Found**: {report.total_problems} ({len(report.errors)} errors, {len(report.warnings)} warnings)",
            f"- **Project Profile**: {report.project_info.summary_stack}",
            f"",
            f"---",
            f"",
            f"## Identified Problems",
            f"",
        ]

        if not report.problems:
            lines.append("All checks passed successfully! Machine and project are in a healthy state.")
        else:
            for diag in report.problems:
                icon = "❌" if diag.is_error else "⚠️"
                lines.append(f"### {icon} {diag.title}")
                lines.append(f"")
                lines.append(f"**Problem**: {diag.message}")
                if diag.why:
                    lines.append(f"")
                    lines.append(f"> **Why**: {diag.why}")
                if diag.evidence:
                    lines.append(f"")
                    lines.append(f"```\n{diag.evidence}\n```")
                if diag.fix:
                    lines.append(f"")
                    lines.append(f"**Recommended Fix**:")
                    lines.append(f"```bash\n{diag.command or diag.fix}\n```")
                lines.append(f"")
                lines.append(f"*Confidence: {diag.confidence.value}*")
                lines.append(f"")
                lines.append("---")
                lines.append("")

        lines.append("## Passed Checks")
        lines.append("")
        for diag in report.passed:
            lines.append(f"- ✓ **{diag.title}**: {diag.message}")

        return "\n".join(lines)
