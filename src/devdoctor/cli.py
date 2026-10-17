"""Command-line interface for DevDoctor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from devdoctor import __version__
from devdoctor.fixer import Fixer
from devdoctor.project import detect_project
from devdoctor.reporter import Reporter
from devdoctor.scanner import Scanner

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

console = Console(legacy_windows=False)
reporter = Reporter(console)


def create_parser() -> argparse.ArgumentParser:
    """Construct the command line argument parser for DevDoctor."""
    parser = argparse.ArgumentParser(
        prog="devdoctor",
        description="Deterministic developer machine and project diagnostic doctor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"DevDoctor {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. scan (default command)
    scan_parser = subparsers.add_parser("scan", help="Scan developer machine and project for issues.")
    scan_parser.add_argument("path", nargs="?", default=".", help="Path to project directory (default: current directory)")
    scan_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    scan_parser.add_argument("--markdown", action="store_true", help="Output GitHub-flavored Markdown")
    scan_parser.add_argument("-v", "--verbose", action="store_true", help="Show comprehensive diagnostic breakdown (WHY, EVIDENCE, FIX, COMMAND)")
    scan_parser.add_argument("-o", "--output", help="Save diagnostic report to a specified file")
    scan_parser.add_argument("--strict", action="store_true", help="Exit with code 1 if any warnings or errors are found")
    scan_parser.add_argument("--checks-dir", help="Path to custom check plugins directory")

    # 2. fix
    fix_parser = subparsers.add_parser("fix", help="Interactively or automatically apply safe fixes for identified problems.")
    fix_parser.add_argument("path", nargs="?", default=".", help="Path to project directory")
    fix_parser.add_argument("--safe", action="store_true", help="Apply only safe, non-destructive automatic fixes")
    fix_parser.add_argument("--dry-run", action="store_true", help="Show planned fixes without modifying anything")
    fix_parser.add_argument("-y", "--yes", action="store_true", help="Confirm all fixes without interactive prompt")

    # 3. dependencies
    dep_parser = subparsers.add_parser("dependencies", help="Check for dependency conflicts and broken imports.")
    dep_parser.add_argument("path", nargs="?", default=".", help="Path to project directory")
    dep_parser.add_argument("-v", "--verbose", action="store_true", help="Show full evidence and fix commands")
    dep_parser.add_argument("--json", action="store_true", help="Output dependency report as JSON")

    # 4. port
    port_parser = subparsers.add_parser("port", help="Network port tools and process management.")
    port_sub = port_parser.add_subparsers(dest="port_action", required=True)
    port_free_parser = port_sub.add_parser("free", help="Safely terminate process occupying a port.")
    port_free_parser.add_argument("port_number", type=int, help="Port number to free (e.g. 8000)")
    port_free_parser.add_argument("-y", "--yes", action="store_true", help="Terminate without interactive prompt")

    # 5. project
    proj_parser = subparsers.add_parser("project", help="Inspect detected project type, framework, and tech stack.")
    proj_parser.add_argument("path", nargs="?", default=".", help="Path to project directory")
    proj_parser.add_argument("--json", action="store_true", help="Output project profile as JSON")

    # 6. report
    rep_parser = subparsers.add_parser("report", help="Generate full diagnostic report in Markdown or JSON format.")
    rep_parser.add_argument("path", nargs="?", default=".", help="Path to project directory")
    rep_parser.add_argument("--format", choices=["terminal", "markdown", "json"], default="markdown", help="Output format")
    rep_parser.add_argument("-o", "--output", help="Output file path (default: stdout)")

    # 7. Framework commands
    for fw in ["django", "fastapi", "docker", "postgres", "redis"]:
        fw_parser = subparsers.add_parser(fw, help=f"Run diagnostics specifically for {fw.capitalize()}.")
        fw_parser.add_argument("path", nargs="?", default=".", help="Path to project directory")
        fw_parser.add_argument("-v", "--verbose", action="store_true", help="Show full diagnostics")
        fw_parser.add_argument("--json", action="store_true", help="Output as JSON")

    return parser


def cmd_scan(args: argparse.Namespace) -> int:
    """Execute devdoctor scan."""
    project_path = Path(args.path).resolve()
    checks_dir = Path(args.checks_dir).resolve() if getattr(args, "checks_dir", None) else None

    scanner = Scanner(project_path, custom_checks_dir=checks_dir)
    report = scanner.scan()

    if getattr(args, "json", False):
        output = reporter.render_json(report)
        if getattr(args, "output", None):
            Path(args.output).write_text(output, encoding="utf-8")
            console.print(f"[green]Report saved to {args.output}[/green]")
        else:
            print(output)
    elif getattr(args, "markdown", False):
        output = reporter.render_markdown(report)
        if getattr(args, "output", None):
            Path(args.output).write_text(output, encoding="utf-8")
            console.print(f"[green]Report saved to {args.output}[/green]")
        else:
            print(output)
    else:
        reporter.render_terminal(report, verbose=getattr(args, "verbose", False))
        if getattr(args, "output", None):
            Path(args.output).write_text(reporter.render_markdown(report), encoding="utf-8")
            console.print(f"[dim]Markdown copy saved to {args.output}[/dim]")

    if getattr(args, "strict", False):
        return 1 if report.total_problems > 0 else 0
    return 1 if report.errors else 0


def cmd_fix(args: argparse.Namespace) -> int:
    """Execute devdoctor fix."""
    project_path = Path(args.path).resolve()
    scanner = Scanner(project_path)
    report = scanner.scan()
    context = scanner.create_context()

    fixer = Fixer(console)
    plan = fixer.build_plan(report)

    safe_only = getattr(args, "safe", False)
    dry_run = getattr(args, "dry_run", False)
    auto_yes = getattr(args, "yes", False)

    res = fixer.execute_plan(
        plan=plan,
        context=context,
        safe_only=safe_only,
        dry_run=dry_run,
        auto_yes=auto_yes,
        interactive=not auto_yes and not dry_run,
    )
    return 0 if len(res.failed) == 0 else 1


def cmd_dependencies(args: argparse.Namespace) -> int:
    """Execute devdoctor dependencies."""
    project_path = Path(args.path).resolve()
    scanner = Scanner(project_path)
    report = scanner.scan(check_names={"dependency_conflicts", "broken_imports"})

    if getattr(args, "json", False):
        print(reporter.render_json(report))
        return 0

    console.print("[bold cyan]DevDoctor Dependency Diagnostics[/bold cyan]")
    console.print("──────────────────────────────────────────\n")

    if not report.problems:
        console.print("[bold green]✓ No dependency conflicts or broken imports detected.[/bold green]")
        return 0

    for d in report.problems:
        sym = "[red]❌[/red]" if d.is_error else "[yellow]⚠[/yellow]"
        console.print(f"{sym} [bold]{d.title}[/bold]\n")
        if d.evidence:
            for line in d.evidence.splitlines():
                console.print(f"{line}")
            console.print()
        elif d.message:
            console.print(f"{d.message}\n")

        if d.fix:
            console.print(f"[bold]Suggested action:[/bold]\n{d.fix}\n")

    return 1 if report.errors else 0


def cmd_port(args: argparse.Namespace) -> int:
    """Execute devdoctor port free <port>."""
    if args.port_action == "free":
        port = args.port_number
        auto_yes = getattr(args, "yes", False)
        fixer = Fixer(console)
        success = fixer.free_port_interactive(port, auto_yes=auto_yes)
        return 0 if success else 1
    return 0


def cmd_project(args: argparse.Namespace) -> int:
    """Execute devdoctor project."""
    project_path = Path(args.path).resolve()
    info = detect_project(project_path)

    if getattr(args, "json", False):
        import json
        print(json.dumps(info.to_dict(), indent=2))
        return 0

    console.print(f"[bold cyan]Project Profile: {info.name}[/bold cyan]")
    console.print("──────────────────────────────────────────")
    console.print(f"[bold]Detected Type:[/bold]      {info.project_type or 'Generic Python'}")
    console.print(f"[bold]Stack Summary:[/bold]      {info.summary_stack}")
    console.print(f"[bold]Technologies:[/bold]       {', '.join(info.technologies) if info.technologies else 'None'}")
    console.print(f"[bold]Frameworks:[/bold]         {', '.join(info.frameworks) if info.frameworks else 'None'}")
    console.print(f"[bold]Config Files:[/bold]       {', '.join(info.config_files) if info.config_files else 'None'}")
    console.print(f"[bold]Dependencies:[/bold]       {len(info.dependencies)} declared")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Execute devdoctor report."""
    project_path = Path(args.path).resolve()
    scanner = Scanner(project_path)
    report = scanner.scan()

    fmt = getattr(args, "format", "markdown")
    if fmt == "json":
        output = reporter.render_json(report)
    elif fmt == "markdown":
        output = reporter.render_markdown(report)
    else:
        reporter.render_terminal(report, verbose=True)
        return 0

    if getattr(args, "output", None):
        Path(args.output).write_text(output, encoding="utf-8")
        console.print(f"[bold green]Report saved to {args.output}[/bold green]")
    else:
        print(output)
    return 0


def cmd_framework(name: str, args: argparse.Namespace) -> int:
    """Execute framework diagnostic command."""
    project_path = Path(args.path).resolve()
    scanner = Scanner(project_path)
    report = scanner.scan(check_names={name})

    if getattr(args, "json", False):
        print(reporter.render_json(report))
        return 0

    console.print(f"[bold cyan]DevDoctor: {name.capitalize()} Diagnostics[/bold cyan]")
    console.print("──────────────────────────────────────────\n")

    if not report.diagnostics:
        console.print(f"[dim]No specific {name} checks triggered.[/dim]")
        return 0

    if report.passed:
        for p in report.passed:
            console.print(f"[green]✓[/green] {p.title}")
        console.print()

    if report.problems:
        for d in report.problems:
            sym = "[red]❌[/red]" if d.is_error else "[yellow]⚠[/yellow]"
            console.print(f"{sym} [bold]{d.title}[/bold]")
            if d.message:
                console.print(f"   {d.message}\n")
            if d.evidence:
                console.print(f"   {d.evidence}\n")
            if d.fix:
                console.print(f"   Fix:\n     {d.fix}\n")
    else:
        console.print(f"[bold green]✓ All {name} diagnostics passed![/bold green]")

    return 1 if report.errors else 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for DevDoctor."""
    if argv is None:
        argv = sys.argv[1:]

    # Default to 'scan' if no arguments or flags provided
    if not argv:
        argv = ["scan"]
    elif argv[0].startswith("-") and argv[0] not in ("-h", "--help", "-V", "--version"):
        argv = ["scan"] + argv

    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "fix":
        return cmd_fix(args)
    elif args.command == "dependencies":
        return cmd_dependencies(args)
    elif args.command == "port":
        return cmd_port(args)
    elif args.command == "project":
        return cmd_project(args)
    elif args.command == "report":
        return cmd_report(args)
    elif args.command in ("django", "fastapi", "docker", "postgres", "redis"):
        return cmd_framework(args.command, args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
