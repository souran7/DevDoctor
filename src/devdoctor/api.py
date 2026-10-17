"""Public Python API for DevDoctor programmatic integration."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set, Union

from devdoctor.checks.base import Check, check, get_registered_checks, register_check
from devdoctor.fixer import FixResult, Fixer
from devdoctor.models import (
    Confidence,
    Diagnostic,
    DiagnosticReport,
    FixAction,
    ProjectInfo,
    ScanContext,
    Severity,
)
from devdoctor.project import detect_project
from devdoctor.reporter import Reporter
from devdoctor.scanner import Scanner


class DevDoctor:
    """High-level Python API for running DevDoctor scans, fixes, and inspections programmatically."""

    def __init__(
        self,
        project_path: Union[str, Path] = ".",
        custom_checks_dir: Optional[Union[str, Path]] = None,
    ):
        self.project_path = Path(project_path).resolve()
        self.custom_checks_dir = Path(custom_checks_dir).resolve() if custom_checks_dir else None
        self.scanner = Scanner(self.project_path, self.custom_checks_dir)
        self.reporter = Reporter()
        self.fixer = Fixer()

    def detect_project(self) -> ProjectInfo:
        """Analyze project files and detect framework/technologies."""
        return detect_project(self.project_path)

    def scan(
        self,
        categories: Optional[List[str]] = None,
        check_names: Optional[List[str]] = None,
        include_frameworks: bool = True,
    ) -> DiagnosticReport:
        """Run diagnostic scan and return structured report."""
        cat_set = set(categories) if categories else None
        chk_set = set(check_names) if check_names else None
        return self.scanner.scan(
            categories=cat_set,
            check_names=chk_set,
            include_frameworks=include_frameworks,
        )

    def fix(
        self,
        safe_only: bool = False,
        dry_run: bool = False,
        auto_yes: bool = True,
        interactive: bool = False,
    ) -> FixResult:
        """Generate and execute fixes for current project diagnostics."""
        report = self.scan()
        context = self.scanner.create_context()
        plan = self.fixer.build_plan(report)
        return self.fixer.execute_plan(
            plan=plan,
            context=context,
            safe_only=safe_only,
            dry_run=dry_run,
            auto_yes=auto_yes,
            interactive=interactive,
        )

    def free_port(self, port: int, auto_yes: bool = True) -> bool:
        """Terminate process occupying the specified port."""
        return self.fixer.free_port_interactive(port, auto_yes=auto_yes)


__all__ = [
    "DevDoctor",
    "Diagnostic",
    "DiagnosticReport",
    "FixAction",
    "ProjectInfo",
    "ScanContext",
    "Severity",
    "Confidence",
    "Check",
    "check",
    "register_check",
    "get_registered_checks",
    "FixResult",
]
