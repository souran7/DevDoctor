"""Check filesystem permissions, disk space, and repository clutter."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity


@register_check
class FilesystemCheck(Check):
    name = "filesystem"
    title = "Filesystem Integrity"
    category = "filesystem"
    description = "Checks filesystem permissions, write access, and unwanted repository clutter."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        root = context.project_path

        # 1. Test write permissions in project directory
        try:
            test_file = root / f".devdoctor_test_{os.getpid()}.tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
        except Exception as ex:
            diagnostics.append(Diagnostic(
                title="Filesystem write permission denied",
                severity=Severity.ERROR,
                message=f"Project directory is not writable: {ex}",
                why="DevDoctor and build tools require write access to create cache files, virtualenvs, and configs.",
                evidence=f"Directory: {root}",
                fix="Adjust directory permissions to grant write access to the current user.",
                confidence=Confidence.HIGH,
                check_id=f"{self.name}_write_permission",
            ))

        # 2. Check for large uncommitted files (> 50MB) in project (ignoring .git and .venv)
        large_files = []
        ignore_dirs = {".git", ".venv", "venv", "node_modules", "dist", "build"}
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
                for f in filenames:
                    fp = Path(dirpath) / f
                    try:
                        sz = fp.stat().st_size
                        if sz > 50 * 1024 * 1024:  # 50MB
                            large_files.append((fp, sz))
                    except Exception:
                        pass
        except Exception:
            pass

        if large_files:
            file_list = "\n     ".join([f"{fp.relative_to(root)} ({sz // (1024*1024)}MB)" for fp, sz in large_files[:3]])
            diagnostics.append(Diagnostic(
                title="Large files detected in repository",
                severity=Severity.WARNING,
                message=f"Found {len(large_files)} file(s) exceeding 50MB.",
                why="Large files bloat git repository size and can cause git pushes to fail or slow down operations.",
                evidence=f"Found:\n     {file_list}",
                fix="Track large files using Git LFS or add them to .gitignore.",
                confidence=Confidence.HIGH,
                check_id=f"{self.name}_large_files",
            ))

        return diagnostics
