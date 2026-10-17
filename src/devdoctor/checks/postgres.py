"""PostgreSQL service and connection diagnostics."""

from __future__ import annotations

import re
import socket
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity
from devdoctor.utils.platform_info import is_windows
from devdoctor.utils.process_utils import is_port_in_use


@register_check
class PostgresCheck(Check):
    name = "postgres"
    title = "PostgreSQL Diagnostics"
    category = "framework"
    description = "Checks PostgreSQL service availability, port 5432 reachability, and configuration."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        is_postgres_project = context.project_info and "PostgreSQL" in context.project_info.technologies

        # Check port 5432
        port_open = is_port_in_use(5432)

        if port_open:
            diagnostics.append(Diagnostic(
                title="PostgreSQL service listening",
                severity=Severity.OK,
                message="PostgreSQL server is listening on port 5432.",
                check_id=f"{self.name}_port_ok",
            ))
        elif is_postgres_project:
            start_cmd = "docker compose up -d postgres" if (context.project_path / "docker-compose.yml").exists() else ("net start postgresql-x64" if is_windows() else "sudo systemctl start postgresql")
            diagnostics.append(Diagnostic(
                title="PostgreSQL not running",
                severity=Severity.ERROR,
                message="PostgreSQL service is not listening on default port 5432.",
                why="The project requires PostgreSQL, but no service was detected on port 5432.",
                evidence="Port 5432 connection refused.",
                fix=f"Start PostgreSQL service:\n     {start_cmd}",
                command=start_cmd,
                confidence=Confidence.HIGH,
                check_id=f"{self.name}_not_running",
            ))

        # Check DATABASE_URL format if present in env
        db_url = context.env_vars.get("DATABASE_URL")
        if db_url:
            if not re.match(r"^postgres(ql)?:\/\/", db_url):
                diagnostics.append(Diagnostic(
                    title="Malformed DATABASE_URL",
                    severity=Severity.WARNING,
                    message="DATABASE_URL does not start with postgres:// or postgresql://.",
                    why=f"DATABASE_URL value is '{db_url[:15]}...', which might not be a valid PostgreSQL connection string.",
                    evidence=f"DATABASE_URL = {db_url}",
                    fix="Verify and correct the connection URL in .env.",
                    confidence=Confidence.MEDIUM,
                    check_id=f"{self.name}_malformed_url",
                ))

        return diagnostics
