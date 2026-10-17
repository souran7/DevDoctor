"""Django framework diagnostic checks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity


@register_check
class DjangoCheck(Check):
    name = "django"
    title = "Django Framework Diagnostics"
    category = "framework"
    description = "Checks Django security settings, secret key, allowed hosts, and migration state."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        root = context.project_path

        manage_py = root / "manage.py"
        is_django = manage_py.is_file() or (context.project_info and "Django" in context.project_info.frameworks)

        if not is_django:
            return diagnostics

        # Search for settings.py
        settings_files = list(root.glob("**/settings.py"))
        # Filter out venvs
        settings_files = [f for f in settings_files if not any(x in f.parts for x in [".venv", "venv", "build"])]

        for sf in settings_files:
            try:
                content = sf.read_text(encoding="utf-8", errors="replace")
                rel_path = sf.relative_to(root)

                # 1. DEBUG = True check
                if re.search(r"^\s*DEBUG\s*=\s*True", content, re.MULTILINE):
                    diagnostics.append(Diagnostic(
                        title="Django DEBUG is True",
                        severity=Severity.WARNING,
                        message="DEBUG is set to True in Django settings.",
                        why="Running with DEBUG=True in production exposes sensitive tracebacks, settings, and database schema to users.",
                        evidence=f"Found in:\n     {rel_path}",
                        fix="Set DEBUG via environment variable:\n     DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1')",
                        confidence=Confidence.HIGH,
                        check_id=f"{self.name}_debug_true",
                        metadata={"file": str(rel_path)},
                    ))

                # 2. Insecure SECRET_KEY check
                if "django-insecure-" in content:
                    diagnostics.append(Diagnostic(
                        title="Insecure Django SECRET_KEY",
                        severity=Severity.WARNING,
                        message="SECRET_KEY appears to be using the default development value.",
                        why="Using a hardcoded or django-insecure secret key compromises session signing and CSRF tokens.",
                        evidence=f"Found in:\n     {rel_path}",
                        fix="Load SECRET_KEY from environment:\n     SECRET_KEY = os.environ['DJANGO_SECRET_KEY']",
                        confidence=Confidence.HIGH,
                        check_id=f"{self.name}_secret_key",
                        metadata={"file": str(rel_path)},
                    ))

                # 3. ALLOWED_HOSTS check
                allowed_match = re.search(r"^\s*ALLOWED_HOSTS\s*=\s*\[(.*?)\]", content, re.MULTILINE | re.DOTALL)
                if allowed_match:
                    hosts_inner = allowed_match.group(1).strip()
                    if not hosts_inner:
                        diagnostics.append(Diagnostic(
                            title="Django ALLOWED_HOSTS is empty",
                            severity=Severity.WARNING,
                            message="ALLOWED_HOSTS is empty.",
                            why="When DEBUG is False, an empty ALLOWED_HOSTS list will block all incoming HTTP requests.",
                            evidence=f"Found in:\n     {rel_path}",
                            fix="Configure ALLOWED_HOSTS:\n     ALLOWED_HOSTS = ['localhost', '127.0.0.1']",
                            confidence=Confidence.HIGH,
                            check_id=f"{self.name}_allowed_hosts",
                            metadata={"file": str(rel_path)},
                        ))
            except Exception:
                pass

        # 4. Check migrations if manage.py is present
        if manage_py.is_file():
            try:
                res = subprocess.run(
                    [sys.executable, str(manage_py), "showmigrations", "--plan"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    cwd=str(root),
                )
                if res.returncode == 0:
                    unapplied = [line for line in res.stdout.splitlines() if "[ ]" in line]
                    if unapplied:
                        diagnostics.append(Diagnostic(
                            title="Unapplied Django migrations",
                            severity=Severity.WARNING,
                            message=f"{len(unapplied)} unapplied database migration(s) detected.",
                            why="Running without applied migrations causes database errors or missing tables.",
                            evidence="\n     ".join(unapplied[:3]),
                            fix="Apply migrations:\n     python manage.py migrate",
                            command=f"{sys.executable} manage.py migrate",
                            confidence=Confidence.HIGH,
                            fix_action=FixAction(
                                description="Run python manage.py migrate",
                                command=f"{sys.executable} manage.py migrate",
                                safe=False,
                            ),
                            check_id=f"{self.name}_migrations",
                        ))
                    else:
                        diagnostics.append(Diagnostic(
                            title="Django migrations",
                            severity=Severity.OK,
                            message="Migrations are up to date.",
                            check_id=f"{self.name}_migrations_ok",
                        ))
            except Exception:
                pass

        return diagnostics
