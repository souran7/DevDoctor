"""Check virtual environment activation and isolation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity
from devdoctor.utils.platform_info import (
    find_local_venv,
    get_venv_activation_command,
    is_in_virtualenv,
    is_windows,
)


@register_check
class VirtualenvCheck(Check):
    name = "virtual_environment"
    title = "Virtual Environment"
    category = "environment"
    description = "Verifies that the shell is operating within an active virtual environment."

    def run(self, context: ScanContext) -> Diagnostic:
        in_venv = is_in_virtualenv()
        context.is_venv = in_venv

        if in_venv:
            venv_name = os.environ.get("VIRTUAL_ENV") or sys.prefix
            venv_display = Path(venv_name).name if venv_name else "active"
            return Diagnostic(
                title=f"Virtual environment ({venv_display})",
                severity=Severity.OK,
                message="Current shell is using an active virtual environment.",
                check_id=self.name,
                metadata={"venv_path": venv_name},
            )

        # Not in virtual environment
        local_venv = find_local_venv(context.project_path)
        venv_dir = local_venv.name if local_venv else ".venv"

        if is_windows():
            fix_text = f"Windows:\n     {venv_dir}\\Scripts\\activate"
            activate_cmd = f"{venv_dir}\\Scripts\\activate"
        else:
            fix_text = f"Linux / macOS:\n     source {venv_dir}/bin/activate"
            activate_cmd = f"source {venv_dir}/bin/activate"

        if not local_venv:
            create_cmd = f"{sys.executable} -m venv .venv"
            fix_text = f"Create and activate virtualenv:\n     {create_cmd}\n     {activate_cmd}"
            fix_action = FixAction(
                description="Create .venv virtual environment",
                command=create_cmd,
                safe=True,
            )
        else:
            fix_action = FixAction(
                description=f"Activate existing {venv_dir} environment",
                command=activate_cmd,
                safe=True,
            )

        return Diagnostic(
            title="Virtual environment",
            severity=Severity.ERROR,
            message="Current shell is not using a virtual environment.",
            why="Installing packages or running tasks outside a virtual environment pollutes the global Python installation and causes dependency collisions.",
            evidence=f"Active interpreter is global: {sys.executable}",
            fix=fix_text,
            command=activate_cmd,
            confidence=Confidence.HIGH,
            fix_action=fix_action,
            check_id=self.name,
            metadata={"local_venv_found": local_venv is not None},
        )
