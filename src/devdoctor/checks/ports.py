"""Check port availability and detect process conflicts."""

from __future__ import annotations

import re
from typing import List, Set

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity
from devdoctor.utils.process_utils import get_port_listener_info, is_port_in_use


@register_check
class PortConflictsCheck(Check):
    name = "port_conflicts"
    title = "Port Conflicts"
    category = "network"
    description = "Checks common development ports for process occupation and port collisions."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []

        # Determine ports to check based on project and common dev ports
        target_ports: Set[int] = set()

        # Check project type defaults
        proj = context.project_info
        if proj:
            if proj.project_type in ("Django", "FastAPI"):
                target_ports.add(8000)
            elif proj.project_type == "Flask":
                target_ports.add(5000)
            if "Node.js" in proj.technologies:
                target_ports.update([3000, 5173])

        # Check .env for PORT=...
        if context.env_vars:
            for k, v in context.env_vars.items():
                if "PORT" in k:
                    try:
                        p = int(v.strip())
                        if 1 <= p <= 65535:
                            target_ports.add(p)
                    except ValueError:
                        pass

        # If no specific ports found, check the standard dev ports
        if not target_ports:
            target_ports = {8000, 3000, 5000, 5173, 8080}

        for port in sorted(list(target_ports)):
            if is_port_in_use(port):
                info = get_port_listener_info(port)
                proc_name = info.process_name if info else "unknown"
                pid = info.pid if info else 0

                evidence_lines = []
                if proc_name and proc_name != "unknown":
                    evidence_lines.append(f"Process: {proc_name}")
                if pid > 0:
                    evidence_lines.append(f"PID: {pid}")

                evidence_text = "\n   ".join(evidence_lines) if evidence_lines else "Listening on local interface"
                fix_cmd = f"devdoctor port free {port}"

                fix_action = None
                if pid > 0:
                    fix_action = FixAction(
                        description=f"Kill process {proc_name} (PID: {pid}) on port {port}",
                        command=fix_cmd,
                        safe=False,
                        action_type="kill_process",
                        metadata={"port": port, "pid": pid, "process_name": proc_name},
                    )

                diagnostics.append(Diagnostic(
                    title=f"Port {port}",
                    severity=Severity.WARNING,
                    message="Port is already occupied.",
                    why=f"Another process ({proc_name}) is already listening on port {port}, which prevents starting the local dev server.",
                    evidence=evidence_text,
                    fix=f"devdoctor port free {port}",
                    command=fix_cmd,
                    confidence=Confidence.HIGH,
                    fix_action=fix_action,
                    check_id=f"{self.name}_{port}",
                    metadata={"port": port, "pid": pid, "process_name": proc_name},
                ))

        return diagnostics
