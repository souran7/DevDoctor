"""Core data models for DevDoctor diagnostics, reports, and fix actions."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class Severity(str, Enum):
    """Diagnostic severity levels."""
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Confidence(str, Enum):
    """Confidence rating for diagnostic conclusions."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class FixAction:
    """An executable or proposed fix action for an identified problem."""
    description: str
    command: Optional[str] = None
    safe: bool = True
    action_type: str = "command"  # "command", "file_create", "file_append", "kill_process", "custom"
    target_path: Optional[Path] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable[[ScanContext], bool]] = None

    def execute(self, context: ScanContext) -> bool:
        """Execute the fix safely."""
        if self.handler:
            return self.handler(context)

        if self.action_type == "file_create" and self.target_path:
            if not self.target_path.exists():
                self.target_path.parent.mkdir(parents=True, exist_ok=True)
                self.target_path.write_text(self.content or "", encoding="utf-8")
                return True
            return False

        if self.action_type == "file_append" and self.target_path:
            self.target_path.parent.mkdir(parents=True, exist_ok=True)
            current = self.target_path.read_text(encoding="utf-8") if self.target_path.exists() else ""
            if self.content and self.content not in current:
                with open(self.target_path, "a", encoding="utf-8") as f:
                    if current and not current.endswith("\n"):
                        f.write("\n")
                    f.write(self.content + "\n")
                return True
            return False

        if self.action_type == "kill_process" and "pid" in self.metadata:
            pid = int(self.metadata["pid"])
            from devdoctor.utils.process_utils import kill_process_by_pid
            return kill_process_by_pid(pid)

        if self.action_type == "command" and self.command:
            import subprocess
            try:
                subprocess.run(self.command, shell=True, check=True, cwd=str(context.project_path))
                return True
            except Exception:
                return False

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "command": self.command,
            "safe": self.safe,
            "action_type": self.action_type,
            "target_path": str(self.target_path) if self.target_path else None,
            "metadata": self.metadata,
        }


@dataclass
class Diagnostic:
    """Represents a single diagnostic result from a check."""
    title: str
    severity: Severity = Severity.OK
    message: str = ""
    why: Optional[str] = None
    evidence: Optional[str] = None
    fix: Optional[str] = None
    command: Optional[str] = None
    confidence: Confidence = Confidence.HIGH
    fix_action: Optional[FixAction] = None
    check_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return self.severity == Severity.OK

    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING

    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR

    @property
    def is_problem(self) -> bool:
        return self.severity in (Severity.WARNING, Severity.ERROR)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "severity": self.severity.value,
            "message": self.message,
            "why": self.why,
            "evidence": self.evidence,
            "fix": self.fix,
            "command": self.command,
            "confidence": self.confidence.value,
            "check_id": self.check_id,
            "has_fix": self.fix_action is not None,
            "fix_action": self.fix_action.to_dict() if self.fix_action else None,
            "metadata": self.metadata,
        }


@dataclass
class ProjectInfo:
    """Metadata regarding the project under inspection."""
    root: Path
    name: str = "project"
    project_type: Optional[str] = None
    technologies: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)

    @property
    def summary_stack(self) -> str:
        """Returns readable tech stack string like 'Django + PostgreSQL + Redis'."""
        items = []
        if self.project_type and self.project_type not in ("Generic Python", "Unknown"):
            items.append(self.project_type)
        for t in self.technologies:
            if t not in items and t.lower() != "python":
                items.append(t)
        return " + ".join(items) if items else (self.project_type or "Python Project")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": str(self.root),
            "name": self.name,
            "project_type": self.project_type,
            "technologies": self.technologies,
            "frameworks": self.frameworks,
            "config_files": self.config_files,
            "dependencies_count": len(self.dependencies),
            "summary_stack": self.summary_stack,
        }


@dataclass
class ScanContext:
    """Context passed to each diagnostic check during scanning."""
    project_path: Path
    python_executable: str = field(default_factory=lambda: sys.executable)
    python_version: str = field(default_factory=lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    is_venv: bool = False
    project_info: Optional[ProjectInfo] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)

    def get_cached(self, key: str, default: Any = None) -> Any:
        return self.cache.get(key, default)

    def set_cached(self, key: str, value: Any) -> None:
        self.cache[key] = value


@dataclass
class DiagnosticReport:
    """Comprehensive diagnostic run report."""
    project_path: Path
    project_info: ProjectInfo
    diagnostics: List[Diagnostic] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    @property
    def passed(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.is_ok]

    @property
    def warnings(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.is_warning]

    @property
    def errors(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.is_error]

    @property
    def problems(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.is_problem]

    @property
    def total_problems(self) -> int:
        return len(self.problems)

    @property
    def is_healthy(self) -> bool:
        return len(self.errors) == 0

    @property
    def score(self) -> int:
        """Deterministic health score from 0 to 100.
        
        Formula:
        Base 100.
        Each error subtracts 12 points.
        Each warning subtracts 4 points.
        Clamped to [0, 100].
        If no problems exist, score is 100.
        """
        if not self.problems:
            return 100
        penalty = (len(self.errors) * 12) + (len(self.warnings) * 4)
        return max(0, min(100, 100 - penalty))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "0.1.0",
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "score": self.score,
            "healthy": self.is_healthy,
            "project_path": str(self.project_path),
            "project": self.project_info.to_dict(),
            "summary": {
                "total": len(self.diagnostics),
                "passed": len(self.passed),
                "warnings": len(self.warnings),
                "errors": len(self.errors),
                "problems": self.total_problems,
            },
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
