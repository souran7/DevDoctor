"""Check Python dependency conflicts and package requirements."""

from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys
from typing import List, Optional

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity


@register_check
class DependencyConflictsCheck(Check):
    name = "dependency_conflicts"
    title = "Dependency Conflicts"
    category = "dependencies"
    description = "Checks for package version conflicts, broken requirements, and pip check incompatibilities."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []

        # 1. Run pip check for active environment consistency
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "check"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # Format: "pkgA 1.0.0 has requirement pkgB<3.0, but you have pkgB 3.1.0."
                    match = re.match(r"^(\S+)\s+(\S+)\s+has requirement\s+([^,]+),\s+but you have\s+(\S+)\s+(\S+)\.?", line)
                    if match:
                        parent_pkg = match.group(1)
                        req_spec = match.group(3).strip()
                        child_pkg = match.group(4)
                        installed_ver = match.group(5).rstrip(".")

                        # Suggested action
                        cmd = f'pip install "{req_spec}"'
                        action = f"Install a compatible version of {child_pkg} matching {req_spec}."

                        evidence = (
                            f"{parent_pkg} requires:\n     {req_spec}\n\n   "
                            f"Installed:\n     {child_pkg} {installed_ver}\n\n   "
                            f"Suggested action:\n     {action}\n\n   "
                            f"Run:\n     {cmd}"
                        )

                        diagnostics.append(Diagnostic(
                            title="Dependency conflict",
                            severity=Severity.ERROR,
                            message=f"{parent_pkg} requires {req_spec}, but {child_pkg} {installed_ver} is installed.",
                            why=f"Incompatible version of {child_pkg} installed in the environment.",
                            evidence=evidence,
                            fix=f"Run:\n     {cmd}",
                            command=cmd,
                            confidence=Confidence.HIGH,
                            fix_action=FixAction(
                                description=f"Align {child_pkg} with {req_spec}",
                                command=cmd,
                                safe=False,
                            ),
                            check_id=f"{self.name}_{parent_pkg}_{child_pkg}",
                            metadata={"parent": parent_pkg, "child": child_pkg, "spec": req_spec, "installed": installed_ver},
                        ))
                    else:
                        diagnostics.append(Diagnostic(
                            title="Dependency conflict",
                            severity=Severity.ERROR,
                            message=line,
                            why="pip check detected an unsatisfied package requirement.",
                            evidence=line,
                            fix="Resolve dependencies using pip install.",
                            confidence=Confidence.HIGH,
                            check_id=f"{self.name}_pip_check",
                        ))
        except Exception:
            pass

        # 2. Check project declared requirements against installed packages
        if context.project_info and context.project_info.dependencies:
            for pkg, spec_str in context.project_info.dependencies.items():
                if spec_str == "*":
                    continue
                try:
                    installed_ver_str = importlib.metadata.version(pkg)
                    installed_ver = Version(installed_ver_str)
                    spec = SpecifierSet(spec_str)
                    if installed_ver not in spec:
                        cmd = f'pip install "{pkg}{spec_str}"'
                        evidence = f"{pkg} declared as: {spec_str}\nInstalled: {installed_ver_str}"
                        diagnostics.append(Diagnostic(
                            title=f"Mismatched package version: {pkg}",
                            severity=Severity.ERROR,
                            message=f"{pkg} requires {spec_str}, but installed version is {installed_ver_str}.",
                            why=f"The project configuration specifies '{pkg}{spec_str}', but the active environment has {installed_ver_str}.",
                            evidence=evidence,
                            fix=f"Reinstall compatible version:\n     {cmd}",
                            command=cmd,
                            confidence=Confidence.HIGH,
                            fix_action=FixAction(
                                description=f"Install {pkg}{spec_str}",
                                command=cmd,
                                safe=False,
                            ),
                            check_id=f"{self.name}_spec_{pkg}",
                        ))
                except importlib.metadata.PackageNotFoundError:
                    # Missing package will also be caught or highlighted here
                    pass
                except (InvalidSpecifier, InvalidVersion):
                    pass

        return diagnostics
