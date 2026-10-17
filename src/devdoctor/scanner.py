"""Scanner engine: coordinates project detection, check execution, and report generation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional, Set

from devdoctor.checks import get_registered_checks
from devdoctor.models import Diagnostic, DiagnosticReport, ScanContext, Severity
from devdoctor.plugin import discover_all_checks
from devdoctor.project import detect_project
from devdoctor.utils.platform_info import get_python_version_str, is_in_virtualenv


class Scanner:
    """Core diagnostic scanner for DevDoctor."""

    def __init__(self, project_path: Optional[Path] = None, custom_checks_dir: Optional[Path] = None):
        self.project_path = (project_path or Path.cwd()).resolve()
        self.custom_checks_dir = custom_checks_dir

    def create_context(self) -> ScanContext:
        """Create and populate the ScanContext for this project."""
        project_info = detect_project(self.project_path)
        return ScanContext(
            project_path=self.project_path,
            is_venv=is_in_virtualenv(),
            python_version=get_python_version_str(),
            project_info=project_info,
        )

    def scan(
        self,
        categories: Optional[Set[str]] = None,
        check_names: Optional[Set[str]] = None,
        include_frameworks: bool = True,
    ) -> DiagnosticReport:
        """Run all diagnostic checks against the target project and produce a report."""
        start_time = time.perf_counter()

        context = self.create_context()
        all_checks = discover_all_checks(self.project_path, self.custom_checks_dir)

        diagnostics: List[Diagnostic] = []

        for chk in all_checks:
            # Check name filter
            if check_names and chk.name not in check_names:
                continue

            # Category filter
            if categories and chk.category not in categories:
                continue

            # Framework checks: only run automatically if the technology is detected in the project
            # or if explicitly requested via check_names / category
            if chk.category == "framework" and not check_names and not categories:
                if not include_frameworks:
                    continue
                # If framework not detected in project_info, skip
                if chk.name == "django" and ("Django" not in (context.project_info.frameworks if context.project_info else [])):
                    continue
                if chk.name == "fastapi" and ("FastAPI" not in (context.project_info.frameworks if context.project_info else [])):
                    continue
                if chk.name == "docker" and ("Docker" not in (context.project_info.technologies if context.project_info else [])):
                    continue
                if chk.name == "postgres" and ("PostgreSQL" not in (context.project_info.technologies if context.project_info else [])):
                    continue
                if chk.name == "redis" and ("Redis" not in (context.project_info.technologies if context.project_info else [])):
                    continue

            try:
                result = chk.run(context)
                if result is None:
                    continue
                elif isinstance(result, list):
                    diagnostics.extend(result)
                elif isinstance(result, Diagnostic):
                    diagnostics.append(result)
            except Exception as e:
                # Fallback diagnostic if check throws an unexpected error
                diagnostics.append(Diagnostic(
                    title=f"Check '{chk.name}' failed to run",
                    severity=Severity.WARNING,
                    message=f"Internal check error: {e}",
                    why=f"An exception occurred inside the check runner for {chk.name}.",
                    check_id=f"error_{chk.name}",
                ))

        duration_ms = (time.perf_counter() - start_time) * 1000

        return DiagnosticReport(
            project_path=self.project_path,
            project_info=context.project_info,
            diagnostics=diagnostics,
            duration_ms=duration_ms,
        )
