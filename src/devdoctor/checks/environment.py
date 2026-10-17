"""Check environment variables, .env file presence, and .env vs .env.example discrepancies."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

from devdoctor.checks.base import Check, register_check
from devdoctor.models import Confidence, Diagnostic, FixAction, ScanContext, Severity
from devdoctor.utils.ast_imports import scan_project_ast
from devdoctor.utils.env_parser import find_missing_env_keys, parse_env_file
from devdoctor.utils.platform_info import is_windows


@register_check
class EnvironmentCheck(Check):
    name = "environment"
    title = "Environment Configuration"
    category = "environment"
    description = "Checks for missing environment files, missing keys from .env.example, and missing required vars found in code."

    def run(self, context: ScanContext) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        project_path = context.project_path

        env_file = project_path / ".env"
        env_example = project_path / ".env.example"

        # Read active environment variables (system + .env if present)
        loaded_env = dict(os.environ)
        if env_file.is_file():
            loaded_env.update(parse_env_file(env_file))
        context.env_vars = loaded_env

        # 1. Check .env vs .env.example
        if env_example.is_file() and not env_file.is_file():
            cp_cmd = "copy .env.example .env" if is_windows() else "cp .env.example .env"
            
            def copy_example_handler(ctx: ScanContext) -> bool:
                try:
                    shutil.copy2(env_example, env_file)
                    return True
                except Exception:
                    return False

            diagnostics.append(Diagnostic(
                title="Environment file missing",
                severity=Severity.ERROR,
                message=".env file is missing, but .env.example exists.",
                why="The project provides a template configuration (.env.example), but no active .env file was found.",
                evidence="Found .env.example, but .env was not found.",
                fix="Create .env from template:\n     " + cp_cmd,
                command=cp_cmd,
                confidence=Confidence.HIGH,
                fix_action=FixAction(
                    description="Copy .env.example to .env",
                    command=cp_cmd,
                    safe=True,
                    handler=copy_example_handler,
                ),
                check_id=f"{self.name}_missing_env_file",
            ))

        elif env_example.is_file() and env_file.is_file():
            missing_from_env = find_missing_env_keys(env_example, env_file)
            for key in missing_from_env:
                def make_add_key_handler(k: str):
                    def handler(ctx: ScanContext) -> bool:
                        try:
                            with open(env_file, "a", encoding="utf-8") as f:
                                f.write(f"\n{k}=\n")
                            return True
                        except Exception:
                            return False
                    return handler

                diagnostics.append(Diagnostic(
                    title="Environment variable",
                    severity=Severity.ERROR,
                    message=f"{key} is required by .env.example but missing in .env.",
                    why=f"{key} is defined in .env.example, indicating it is required for project runtime.",
                    evidence="Defined in: .env.example",
                    fix=f"Add {key} to .env",
                    command=f'echo {key}= >> .env',
                    confidence=Confidence.HIGH,
                    fix_action=FixAction(
                        description=f"Add {key} placeholder to .env",
                        command=f'echo {key}= >> .env',
                        safe=True,
                        handler=make_add_key_handler(key),
                    ),
                    check_id=f"{self.name}_example_{key}",
                    metadata={"var_name": key, "source": ".env.example"},
                ))

        # 2. Check code files for required environment variable accesses (AST)
        _, env_usages = scan_project_ast(project_path)
        reported_vars = set()

        for usage in env_usages:
            var_name = usage.var_name
            # Only strictly required environment variable accesses without defaults
            if not usage.is_required or usage.has_default or var_name in reported_vars:
                continue

            # Check if set in loaded_env
            if var_name not in loaded_env or not loaded_env[var_name].strip():
                reported_vars.add(var_name)
                try:
                    rel_file = usage.file_path.relative_to(project_path)
                except Exception:
                    rel_file = usage.file_path.name
                
                def make_append_var_handler(v: str):
                    def handler(ctx: ScanContext) -> bool:
                        try:
                            target = ctx.project_path / ".env"
                            with open(target, "a", encoding="utf-8") as f:
                                f.write(f"\n{v}=\n")
                            return True
                        except Exception:
                            return False
                    return handler

                diagnostics.append(Diagnostic(
                    title="Environment variable",
                    severity=Severity.ERROR,
                    message=f"{var_name} is required but missing.",
                    why=f"Code in {rel_file} accesses os.environ['{var_name}'] without a default value.",
                    evidence=f"Found in:\n     {rel_file} (line {usage.line_number})",
                    fix=f"Add {var_name} to .env",
                    command=f'echo {var_name}= >> .env',
                    confidence=Confidence.HIGH,
                    fix_action=FixAction(
                        description=f"Add {var_name} to .env",
                        command=f'echo {var_name}= >> .env',
                        safe=True,
                        handler=make_append_var_handler(var_name),
                    ),
                    check_id=f"{self.name}_code_{var_name}",
                    metadata={"var_name": var_name, "found_in": str(rel_file), "line": usage.line_number},
                ))

        return diagnostics
