"""FastAPI framework diagnostic checks."""

from __future__ import annotations

import importlib.util
import re
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity
from devdoctor.utils.ast_imports import collect_python_files
from devdoctor.utils.process_utils import is_port_in_use


@register_check
class FastAPICheck(Check):
    name = "fastapi"
    title = "FastAPI Framework Diagnostics"
    category = "framework"
    description = "Checks FastAPI setup: Uvicorn availability, default port 8000, and CORS configuration."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        is_fastapi = context.project_info and "FastAPI" in context.project_info.frameworks

        if not is_fastapi:
            return diagnostics

        # 1. Uvicorn installed check
        uvicorn_spec = importlib.util.find_spec("uvicorn")
        if uvicorn_spec:
            diagnostics.append(Diagnostic(
                title="Uvicorn installed",
                severity=Severity.OK,
                message="Uvicorn ASGI server is installed.",
                check_id=f"{self.name}_uvicorn_installed",
            ))
        else:
            diagnostics.append(Diagnostic(
                title="Uvicorn not installed",
                severity=Severity.ERROR,
                message="Uvicorn is required to serve FastAPI applications.",
                why="FastAPI applications need an ASGI server like Uvicorn to run.",
                fix="Install uvicorn:\n     pip install 'uvicorn[standard]'",
                command="pip install 'uvicorn[standard]'",
                confidence=Confidence.HIGH,
                fix_action=FixAction(
                    description="Install uvicorn[standard]",
                    command="pip install 'uvicorn[standard]'",
                    safe=False,
                ),
                check_id=f"{self.name}_uvicorn_missing",
            ))

        # 2. Port 8000 check
        if is_port_in_use(8000):
            diagnostics.append(Diagnostic(
                title="Port 8000 occupied",
                severity=Severity.WARNING,
                message="Default FastAPI port (8000) is currently occupied.",
                why="Uvicorn defaults to port 8000; starting a new server without --port will fail.",
                fix="Free port 8000 or specify another port:\n     devdoctor port free 8000",
                command="devdoctor port free 8000",
                confidence=Confidence.HIGH,
                check_id=f"{self.name}_port_8000",
            ))
        else:
            diagnostics.append(Diagnostic(
                title="Port 8000 available",
                severity=Severity.OK,
                message="Port 8000 is free and ready for Uvicorn.",
                check_id=f"{self.name}_port_8000_free",
            ))

        # 3. CORS allows * check
        py_files = collect_python_files(context.project_path)
        for pf in py_files:
            try:
                txt = pf.read_text(encoding="utf-8", errors="replace")
                if 'allow_origins=["*"]' in txt or "allow_origins=['*']" in txt:
                    rel_p = pf.relative_to(context.project_path) if pf.is_relative_to(context.project_path) else pf.name
                    diagnostics.append(Diagnostic(
                        title="CORS allows * wildcard",
                        severity=Severity.WARNING,
                        message="CORS middleware is configured with allow_origins=['*'].",
                        why="Allowing wildcard origins with credentials or in production allows any domain to send authenticated cross-origin requests.",
                        evidence=f"Found in:\n     {rel_p}",
                        fix="Restrict allow_origins to specific frontend domains.",
                        confidence=Confidence.HIGH,
                        check_id=f"{self.name}_cors_wildcard",
                    ))
                    break
            except Exception:
                pass

        return diagnostics
