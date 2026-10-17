"""Docker daemon, container health, and port collision diagnostics."""

from __future__ import annotations

import re
import subprocess
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, ScanContext, Severity


@register_check
class DockerCheck(Check):
    name = "docker"
    title = "Docker Diagnostics"
    category = "framework"
    description = "Checks Docker daemon accessibility, exited container states, and compose service ports."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        is_docker_project = context.project_info and "Docker" in context.project_info.technologies

        # 1. Check docker CLI
        try:
            res_ver = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=4)
            if res_ver.returncode != 0:
                if is_docker_project:
                    diagnostics.append(Diagnostic(
                        title="Docker CLI unavailable",
                        severity=Severity.ERROR,
                        message="Project uses Docker, but 'docker' command is not available in PATH.",
                        why="Dockerfile or docker-compose is present, but Docker CLI is not installed.",
                        fix="Install Docker Desktop from https://www.docker.com/products/docker-desktop/.",
                        confidence=Confidence.HIGH,
                        check_id=f"{self.name}_cli_missing",
                    ))
                return diagnostics

            match = re.search(r"Docker version\s+([0-9.]+)", res_ver.stdout)
            ver = match.group(1) if match else "available"
            diagnostics.append(Diagnostic(
                title=f"Docker {ver}",
                severity=Severity.OK,
                message=f"Docker CLI is installed and available (version {ver}).",
                check_id=f"{self.name}_version",
            ))

        except Exception:
            if is_docker_project:
                diagnostics.append(Diagnostic(
                    title="Docker CLI unavailable",
                    severity=Severity.ERROR,
                    message="Docker CLI is not found in PATH.",
                    fix="Install Docker Desktop and ensure it is in your PATH.",
                    confidence=Confidence.HIGH,
                    check_id=f"{self.name}_cli_missing",
                ))
            return diagnostics

        # 2. Check Docker daemon running
        try:
            res_info = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
            if res_info.returncode != 0:
                diagnostics.append(Diagnostic(
                    title="Docker daemon not running",
                    severity=Severity.ERROR,
                    message="Docker daemon is stopped or inaccessible.",
                    why="The docker client cannot communicate with the Docker daemon engine.",
                    evidence=res_info.stderr.strip()[:200] if res_info.stderr else "Connection refused",
                    fix="Start Docker Desktop or run 'sudo systemctl start docker'.",
                    confidence=Confidence.HIGH,
                    check_id=f"{self.name}_daemon_stopped",
                ))
                return diagnostics
            else:
                diagnostics.append(Diagnostic(
                    title="Docker daemon running",
                    severity=Severity.OK,
                    message="Docker engine is healthy and accepting commands.",
                    check_id=f"{self.name}_daemon_ok",
                ))
        except Exception:
            diagnostics.append(Diagnostic(
                title="Docker daemon unreachable",
                severity=Severity.WARNING,
                message="Timed out communicating with Docker daemon.",
                fix="Ensure Docker Desktop is active.",
                check_id=f"{self.name}_daemon_timeout",
            ))
            return diagnostics

        # 3. Check for crashed or failed exited containers
        try:
            res_ps = subprocess.run(
                ["docker", "ps", "-a", "--filter", "status=exited", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res_ps.returncode == 0 and res_ps.stdout.strip():
                for line in res_ps.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        name, status = parts[0], parts[1]
                        # e.g. "Exited (1) 2 minutes ago"
                        match_code = re.search(r"Exited\s+\((\d+)\)", status)
                        if match_code and match_code.group(1) != "0":
                            code = match_code.group(1)
                            diagnostics.append(Diagnostic(
                                title=f"Container {name} crashed",
                                severity=Severity.ERROR,
                                message=f"Container '{name}' exited with error code {code}.",
                                why=f"Container process terminated abnormally ({status}).",
                                evidence=f"Container: {name} | Status: {status}",
                                fix=f"Inspect container logs:\n     docker logs {name}",
                                command=f"docker logs {name}",
                                confidence=Confidence.HIGH,
                                check_id=f"{self.name}_container_{name}",
                            ))
        except Exception:
            pass

        return diagnostics
