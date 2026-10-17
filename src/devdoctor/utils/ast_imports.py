"""AST-based inspection for Python imports and environment variable accesses."""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

SYSTEM_ENV_VARS = {
    "PATH", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX", "HOME", "USER",
    "USERNAME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP",
    "OS", "SHELL", "TERM", "LANG", "LC_ALL", "SYSTEMROOT", "WINDIR",
}

IGNORE_DIRS = {
    ".venv", "venv", "env", ".env_dir", ".git", ".tox", ".pytest_cache",
    "__pycache__", "node_modules", "dist", "build", ".eggs", ".mypy_cache"
}


@dataclass
class ImportUsage:
    """Record of a module import in a Python file."""
    module_name: str
    file_path: Path
    line_number: int


@dataclass
class EnvVarUsage:
    """Record of an environment variable read in a Python file."""
    var_name: str
    file_path: Path
    line_number: int
    has_default: bool
    is_required: bool  # True if subscript like os.environ['VAR']


def should_skip_path(path: Path) -> bool:
    """Check if the path is within an ignored directory."""
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    return False


def collect_python_files(project_path: Path, max_files: int = 500) -> List[Path]:
    """Find Python source files in the project, ignoring virtualenvs and caches."""
    py_files: List[Path] = []
    try:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                if file.endswith(".py"):
                    full_path = Path(root) / file
                    py_files.append(full_path)
                    if len(py_files) >= max_files:
                        return py_files
    except Exception:
        pass
    return py_files


class SourceVisitor(ast.NodeVisitor):
    """AST visitor that collects imported top-level modules and environment variable lookups."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports: List[ImportUsage] = []
        self.env_vars: List[EnvVarUsage] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            top_level = alias.name.split(".")[0]
            self.imports.append(ImportUsage(module_name=top_level, file_path=self.file_path, line_number=node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level == 0 and node.module:
            top_level = node.module.split(".")[0]
            self.imports.append(ImportUsage(module_name=top_level, file_path=self.file_path, line_number=node.lineno))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        # Detect os.environ['VAR'] or environ['VAR'] -> strictly required, throws KeyError if missing
        var_name = None
        if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
            var_name = self._extract_string_value(node.slice)
        elif isinstance(node.value, ast.Name) and node.value.id == "environ":
            var_name = self._extract_string_value(node.slice)

        if var_name and var_name not in SYSTEM_ENV_VARS:
            self.env_vars.append(EnvVarUsage(
                var_name=var_name,
                file_path=self.file_path,
                line_number=node.lineno,
                has_default=False,
                is_required=True,
            ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Detect os.getenv('VAR', default) or os.environ.get('VAR', default)
        var_name = None
        has_default = len(node.args) > 1 or any(kw.arg == "default" for kw in node.keywords)

        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "getenv" and isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                if node.args:
                    var_name = self._extract_string_value(node.args[0])
            elif node.func.attr == "get" and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "environ":
                if node.args:
                    var_name = self._extract_string_value(node.args[0])
            elif node.func.attr == "get" and isinstance(node.func.value, ast.Name) and node.func.value.id == "environ":
                if node.args:
                    var_name = self._extract_string_value(node.args[0])
        elif isinstance(node.func, ast.Name) and node.func.id == "getenv":
            if node.args:
                var_name = self._extract_string_value(node.args[0])

        if var_name and var_name not in SYSTEM_ENV_VARS:
            self.env_vars.append(EnvVarUsage(
                var_name=var_name,
                file_path=self.file_path,
                line_number=node.lineno,
                has_default=has_default,
                is_required=not has_default,
            ))

        self.generic_visit(node)

    def _extract_string_value(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None


def scan_project_ast(project_path: Path) -> Tuple[List[ImportUsage], List[EnvVarUsage]]:
    """Scan all Python files in the project for imports and environment variable references."""
    py_files = collect_python_files(project_path)
    all_imports: List[ImportUsage] = []
    all_env_vars: List[EnvVarUsage] = []

    for file_path in py_files:
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
            visitor = SourceVisitor(file_path)
            visitor.visit(tree)
            all_imports.extend(visitor.imports)
            all_env_vars.extend(visitor.env_vars)
        except Exception:
            continue

    return all_imports, all_env_vars


def is_local_module(module_name: str, project_path: Path) -> bool:
    """Check if the module corresponds to a local file or package within the project."""
    if (project_path / f"{module_name}.py").is_file():
        return True
    if (project_path / module_name / "__init__.py").is_file():
        return True
    src_dir = project_path / "src"
    if src_dir.is_dir():
        if (src_dir / f"{module_name}.py").is_file():
            return True
        if (src_dir / module_name / "__init__.py").is_file():
            return True
    return False


def is_stdlib_module(module_name: str) -> bool:
    """Check if the module is part of Python's standard library."""
    if hasattr(sys, "stdlib_module_names"):
        return module_name in sys.stdlib_module_names
    return module_name in sys.builtin_module_names


def find_missing_installed_imports(project_path: Path) -> List[Tuple[str, Path, int]]:
    """Identify third-party imports in project code that are not installed in the active environment."""
    imports, _ = scan_project_ast(project_path)
    missing: List[Tuple[str, Path, int]] = []
    checked: Set[str] = set()

    for item in imports:
        mod = item.module_name
        if mod in checked:
            continue
        if is_stdlib_module(mod) or is_local_module(mod, project_path):
            continue

        checked.add(mod)
        try:
            spec = importlib.util.find_spec(mod)
            if spec is None:
                missing.append((mod, item.file_path, item.line_number))
        except Exception:
            missing.append((mod, item.file_path, item.line_number))

    return missing
