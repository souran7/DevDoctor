"""Check for missing or uninstalled Python imports in project code."""

from __future__ import annotations

from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity
from devdoctor.utils.ast_imports import find_missing_installed_imports, get_distribution_name


@register_check
class BrokenImportsCheck(Check):
    name = "broken_imports"
    title = "Python Imports"
    category = "dependencies"
    description = "Scans project Python files for third-party imports that are not installed in the active environment."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        missing = find_missing_installed_imports(context.project_path)

        for mod, file_path, line_no in missing:
            try:
                rel_path = file_path.relative_to(context.project_path)
            except Exception:
                rel_path = file_path.name

            dist_name = get_distribution_name(mod)
            pip_cmd = f"pip install {dist_name}"

            diagnostics.append(Diagnostic(
                title=f"Missing module '{mod}'",
                severity=Severity.ERROR,
                message=f"Module '{mod}' is imported but not installed in current environment.",
                why=f"Code in {rel_path} requires '{mod}', but the package is not found in site-packages.",
                evidence=f"Found in:\n     {rel_path} (line {line_no})",
                fix=f"Install {dist_name} via pip:\n     {pip_cmd}",
                command=pip_cmd,
                confidence=Confidence.HIGH,
                fix_action=FixAction(
                    description=f"Install {dist_name}",
                    command=pip_cmd,
                    safe=False,
                ),
                check_id=f"{self.name}_{mod}",
                metadata={"module": mod, "file": str(rel_path), "line": line_no, "distribution": dist_name},
            ))

        return diagnostics
