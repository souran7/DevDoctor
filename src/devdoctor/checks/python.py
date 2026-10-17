"""Check Python runtime version and project compatibility."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity
from devdoctor.utils.platform_info import get_python_version_str


def get_required_python_spec(project_path: Path) -> Optional[str]:
    """Read Python version requirement from pyproject.toml, .python-version, or runtime.txt."""
    pyproject = project_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            # Match requires-python = ">=3.11"
            match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1).strip()
        except Exception:
            pass

    python_version_file = project_path / ".python-version"
    if python_version_file.is_file():
        try:
            version_str = python_version_file.read_text(encoding="utf-8", errors="replace").strip()
            if version_str:
                return f"=={version_str}" if not any(c in version_str for c in "<>=~") else version_str
        except Exception:
            pass

    runtime_txt = project_path / "runtime.txt"
    if runtime_txt.is_file():
        try:
            content = runtime_txt.read_text(encoding="utf-8", errors="replace").strip()
            # python-3.12.2 -> ==3.12.2
            match = re.search(r"python-([0-9.]+)", content)
            if match:
                return f"=={match.group(1)}"
        except Exception:
            pass

    return None


@register_check
class PythonVersionCheck(Check):
    name = "python_version"
    title = "Python Version"
    category = "system"
    description = "Verifies Python version and project requirement compatibility."

    def run(self, context: ScanContext) -> Diagnostic:
        current_version_str = get_python_version_str()
        current_ver = Version(current_version_str)
        spec_str = get_required_python_spec(context.project_path)

        if spec_str:
            try:
                spec = SpecifierSet(spec_str)
                if current_ver not in spec:
                    return Diagnostic(
                        title="Python version incompatible",
                        severity=Severity.ERROR,
                        message=f"Your project requires Python {spec_str}, but you are running {current_version_str}.",
                        why=f"The current Python runtime ({current_version_str}) does not satisfy the specified version constraints.",
                        evidence=f"Active: {current_version_str} | Required: {spec_str}",
                        fix=f"Install Python {spec_str} and recreate your virtual environment.",
                        command=f"py -{spec_str.replace('>=', '').replace('==', '')} -m venv .venv",
                        confidence=Confidence.HIGH,
                        check_id=self.name,
                        metadata={"current_version": current_version_str, "required_spec": spec_str},
                    )
            except InvalidSpecifier:
                pass

        # Check for ancient / unsupported Python versions (< 3.9)
        if sys.version_info < (3, 9):
            return Diagnostic(
                title=f"Python {current_version_str}",
                severity=Severity.WARNING,
                message=f"Python {current_version_str} is End-Of-Life and no longer receives security updates.",
                why="Python versions below 3.9 are deprecated by python.org and most modern libraries.",
                evidence=f"Active runtime version: {current_version_str}",
                fix="Upgrade to Python 3.11 or 3.12 for improved performance and security.",
                command="py -3.12 -m venv .venv",
                confidence=Confidence.HIGH,
                check_id=self.name,
            )

        return Diagnostic(
            title=f"Python {current_version_str}",
            severity=Severity.OK,
            message=f"Python {current_version_str} is installed and compatible.",
            check_id=self.name,
            metadata={"version": current_version_str},
        )
