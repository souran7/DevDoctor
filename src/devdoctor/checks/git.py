"""Check Git availability, author configuration, and sensitive file tracking."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity


@register_check
class GitCheck(Check):
    name = "git"
    title = "Git Configuration"
    category = "git"
    description = "Verifies Git CLI availability, repository status, and security of sensitive files."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []

        # 1. Check Git CLI availability
        git_version = None
        try:
            res = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                out = res.stdout.strip()
                match = re.search(r"git version\s+([0-9]+(?:\.[0-9]+)+)", out)
                git_version = match.group(1).rstrip(".") if match else "available"
                diagnostics.append(Diagnostic(
                    title=f"Git {git_version}",
                    severity=Severity.OK,
                    message=f"Git is installed and available (version {git_version}).",
                    check_id=f"{self.name}_version",
                    metadata={"version": git_version},
                ))
            else:
                diagnostics.append(Diagnostic(
                    title="Git CLI unavailable",
                    severity=Severity.WARNING,
                    message="Git command failed or is not installed.",
                    why="Git is required for version control, dependency tracking, and release management.",
                    fix="Install Git from https://git-scm.com/downloads.",
                    confidence=Confidence.HIGH,
                    check_id=f"{self.name}_missing",
                ))
                return diagnostics
        except Exception:
            diagnostics.append(Diagnostic(
                title="Git CLI unavailable",
                severity=Severity.WARNING,
                message="Git is not installed or not in PATH.",
                why="Version control commands and repository checks require git.",
                fix="Install Git and ensure it is added to your PATH.",
                confidence=Confidence.HIGH,
                check_id=f"{self.name}_missing",
            ))
            return diagnostics

        # 2. Check if this is a Git repository
        git_dir = context.project_path / ".git"
        if not git_dir.exists():
            return diagnostics

        # Check git config user.name and user.email
        try:
            res_name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, cwd=str(context.project_path))
            res_email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True, cwd=str(context.project_path))
            has_name = bool(res_name.stdout.strip())
            has_email = bool(res_email.stdout.strip())

            if not (has_name and has_email):
                diagnostics.append(Diagnostic(
                    title="Git author configuration",
                    severity=Severity.WARNING,
                    message="Git user.name or user.email is not configured.",
                    why="Commits cannot be properly authored without user name and email configured.",
                    evidence=f"user.name='{res_name.stdout.strip()}', user.email='{res_email.stdout.strip()}'",
                    fix="Set your Git author details:\n     git config --global user.name \"Your Name\"\n     git config --global user.email \"you@example.com\"",
                    command='git config --global user.name "Your Name" && git config --global user.email "you@example.com"',
                    confidence=Confidence.HIGH,
                    check_id=f"{self.name}_author",
                ))
        except Exception:
            pass

        # 3. Check .gitignore for .env
        env_file = context.project_path / ".env"
        gitignore_file = context.project_path / ".gitignore"

        if env_file.is_file():
            # Check if .env is ignored
            is_ignored = False
            if gitignore_file.is_file():
                try:
                    lines = [line.strip() for line in gitignore_file.read_text(encoding="utf-8", errors="replace").splitlines()]
                    is_ignored = any(line in [".env", "*.env", ".env*", "/.env"] for line in lines)
                except Exception:
                    pass

            if not is_ignored:
                diagnostics.append(Diagnostic(
                    title="Sensitive file .env not ignored",
                    severity=Severity.ERROR,
                    message=".env file exists but is not listed in .gitignore, risking secret leaks.",
                    why="Committing .env files exposes sensitive credentials, secret keys, and database passwords in git history.",
                    evidence="Found .env in project root, but '.env' pattern was not found in .gitignore.",
                    fix="Add .env to .gitignore",
                    command="echo .env >> .gitignore",
                    confidence=Confidence.HIGH,
                    fix_action=FixAction(
                        description="Add .env to .gitignore",
                        safe=True,
                        action_type="file_append",
                        target_path=gitignore_file,
                        content=".env",
                    ),
                    check_id=f"{self.name}_gitignore_env",
                ))

            # Check if .env is already tracked in git index
            try:
                res_tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", ".env"],
                    capture_output=True,
                    text=True,
                    cwd=str(context.project_path),
                )
                if res_tracked.returncode == 0:
                    diagnostics.append(Diagnostic(
                        title=".env is tracked by Git",
                        severity=Severity.ERROR,
                        message=".env file is tracked in git index! Secrets may already be committed.",
                        why="A tracked .env will be pushed to remotes, compromising credentials.",
                        evidence="git ls-files .env confirmed tracking.",
                        fix="Remove .env from git cache:\n     git rm --cached .env",
                        command="git rm --cached .env",
                        confidence=Confidence.HIGH,
                        fix_action=FixAction(
                            description="Remove .env from git cache",
                            command="git rm --cached .env",
                            safe=False,
                        ),
                        check_id=f"{self.name}_tracked_env",
                    ))
            except Exception:
                pass

        return diagnostics
