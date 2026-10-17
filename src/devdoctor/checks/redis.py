"""Redis server service and ping diagnostics."""

from __future__ import annotations

import socket
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, ScanContext, Severity
from devdoctor.utils.process_utils import is_port_in_use


@register_check
class RedisCheck(Check):
    name = "redis"
    title = "Redis Diagnostics"
    category = "framework"
    description = "Checks Redis server availability on port 6379 and RESP PING responsiveness."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        is_redis_project = context.project_info and "Redis" in context.project_info.technologies

        # Check port 6379
        port_open = is_port_in_use(6379)

        if port_open:
            # Try raw RESP PING
            ping_ok = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    s.connect(("127.0.0.1", 6379))
                    s.sendall(b"*1\r\n$4\r\nPING\r\n")
                    response = s.recv(1024)
                    if b"+PONG" in response:
                        ping_ok = True
            except Exception:
                pass

            if ping_ok:
                diagnostics.append(Diagnostic(
                    title="Redis healthy",
                    severity=Severity.OK,
                    message="Redis server is running and responded to PING with PONG.",
                    check_id=f"{self.name}_ping_ok",
                ))
            else:
                diagnostics.append(Diagnostic(
                    title="Redis port open",
                    severity=Severity.OK,
                    message="Port 6379 is listening (Redis server active).",
                    check_id=f"{self.name}_port_ok",
                ))

        elif is_redis_project:
            start_cmd = "docker run -d -p 6379:6379 --name redis redis:alpine"
            diagnostics.append(Diagnostic(
                title="Redis not running",
                severity=Severity.ERROR,
                message="Redis server is not listening on default port 6379.",
                why="The project uses Redis, but no local Redis instance is reachable on port 6379.",
                evidence="Port 6379 connection refused.",
                fix=f"Start Redis with Docker:\n     {start_cmd}",
                command=start_cmd,
                confidence=Confidence.HIGH,
                check_id=f"{self.name}_not_running",
            ))

        return diagnostics
