"""Check pip installation and availability."""

from __future__ import annotations

import re
import subprocess
import sys

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity


@register_check
class PipAvailabilityCheck(Check):
    name = "pip_availability"
    title = "pip Availability"
    category = "system"
    description = "Checks that pip is available and functional in the active environment."

    def run(self, context: ScanContext) -> Diagnostic:
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                output = res.stdout.strip()
                # e.g., "pip 25.0.1 from ..."
                match = re.search(r"pip\s+([0-9.]+)", output)
                version_str = match.group(1) if match else "available"
                return Diagnostic(
                    title=f"pip {version_str}",
                    severity=Severity.OK,
                    message=f"pip is installed and functional (version {version_str}).",
                    check_id=self.name,
                    metadata={"version": version_str},
                )
            else:
                return Diagnostic(
                    title="pip unavailable",
                    severity=Severity.ERROR,
                    message="pip command failed to execute in active Python environment.",
                    why="pip might be corrupt or missing in this Python installation.",
                    evidence=res.stderr.strip() or res.stdout.strip(),
                    fix="Run ensurepip to bootstrap pip into this environment.",
                    command=f"{sys.executable} -m ensurepip --upgrade",
                    confidence=Confidence.HIGH,
                    fix_action=FixAction(
                        description="Bootstrap pip via ensurepip",
                        command=f"{sys.executable} -m ensurepip --upgrade",
                        safe=True,
                    ),
                    check_id=self.name,
                )
        except Exception as ex:
            return Diagnostic(
                title="pip unavailable",
                severity=Severity.ERROR,
                message=f"Unable to execute pip: {ex}",
                why="Python executable cannot find or execute the pip module.",
                fix="Bootstrap pip or repair Python installation.",
                command=f"{sys.executable} -m ensurepip --upgrade",
                confidence=Confidence.HIGH,
                check_id=self.name,
            )
