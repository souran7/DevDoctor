"""AST-based inspection for Python imports and environment variable accesses."""

from __future__ import annotations

import ast
import importlib.metadata
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
    "__pycache__", "node_modules", "dist", "build", ".eggs", ".mypy_cache",
    ".idea", ".vscode", ".ruff_cache", ".coverage", "htmlcov", "site-packages",
}


def is_ignored_dir(path: Path) -> bool:
    """Check if directory is an ignored directory or a virtual environment."""
    name = path.name
    if name.startswith(".") or name in IGNORE_DIRS:
        return True
    if (path / "pyvenv.cfg").is_file():
        return True
    if (path / "Scripts" / "python.exe").is_file() or (path / "bin" / "python").is_file():
        return True
    return False


def should_skip_path(path: Path) -> bool:
    """Check if the path is within an ignored directory or a virtual environment."""
    for part in path.parts:
        if part.startswith(".") and part != "." and part != "..":
            return True
        if part in IGNORE_DIRS:
            return True
    curr = path if path.is_dir() else path.parent
    while curr and curr != curr.parent:
        if (curr / "pyvenv.cfg").is_file():
            return True
        curr = curr.parent
    return False


def has_python_files(dir_path: Path) -> bool:
    """Check if dir_path contains at least one Python file directly or in a non-ignored subdirectory."""
    if not dir_path.is_dir() or is_ignored_dir(dir_path):
        return False

    # Check immediate files first for performance
    try:
        with os.scandir(dir_path) as it:
            for entry in it:
                if entry.is_file() and entry.name.endswith((".py", ".pyw", ".pyd", ".so")):
                    return True
    except Exception:
        return False

    # Check subdirectories recursively, pruning ignored folders
    try:
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not is_ignored_dir(Path(root) / d)]
            for file in files:
                if file.endswith((".py", ".pyw", ".pyd", ".so")):
                    return True
    except Exception:
        pass

    return False


def is_package_dir(dir_path: Path) -> bool:
    """Check if a directory is a valid local package (regular with __init__.py or PEP 420 namespace package)."""
    if not dir_path.is_dir():
        return False
    if not dir_path.name.isidentifier():
        return False
    if is_ignored_dir(dir_path):
        return False
    # Regular package has __init__.py
    if (dir_path / "__init__.py").is_file():
        return True
    # Namespace package contains at least one Python source file
    return has_python_files(dir_path)


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


def collect_python_files(project_path: Path, max_files: int = 500) -> List[Path]:
    """Find Python source files in the project, ignoring virtualenvs and caches."""
    py_files: List[Path] = []
    try:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if not is_ignored_dir(Path(root) / d)]
            for file in files:
                if file.endswith((".py", ".pyw")):
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
        # node.level > 0 indicates relative imports (e.g. from . import X or from ..core import Y)
        # Relative imports are project-internal and are never third-party PyPI dependencies.
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


def is_local_module(
    module_name: str,
    project_path: Path,
    file_path: Optional[Path] = None,
) -> bool:
    """Check if the module corresponds to a local file, regular package, or namespace package within the project."""
    if not module_name or not module_name.isidentifier():
        return False

    project_root = project_path.resolve()

    # Collect source roots to check
    source_roots: List[Path] = [project_root]

    # Standard layout directories: src/, lib/
    for sub in ("src", "lib"):
        sub_dir = project_root / sub
        if sub_dir.is_dir() and not is_ignored_dir(sub_dir):
            source_roots.append(sub_dir)

    # If file_path is given, also check its parent directory and ancestors up to project_root
    if file_path is not None:
        try:
            curr = file_path.resolve().parent
            while curr != project_root and curr.is_relative_to(project_root):
                if curr not in source_roots and not is_ignored_dir(curr):
                    source_roots.append(curr)
                curr = curr.parent
        except Exception:
            pass

    # Check each candidate source root
    for root in source_roots:
        # 1. Single-file module: root / module_name.py (or .pyw, .pyd, .so)
        for ext in (".py", ".pyw", ".pyd", ".so"):
            mod_file = root / f"{module_name}{ext}"
            if mod_file.is_file():
                return True

        # 2. Package directory: root / module_name (with __init__.py or namespace package)
        pkg_dir = root / module_name
        if is_package_dir(pkg_dir):
            return True

    # Also check if module_name exists as a module or package inside any top-level source package in project_root or src/
    for base in (project_root, project_root / "src"):
        if not base.is_dir():
            continue
        try:
            for entry in base.iterdir():
                if entry.is_dir() and not is_ignored_dir(entry) and entry.name.isidentifier():
                    for ext in (".py", ".pyw", ".pyd", ".so"):
                        if (entry / f"{module_name}{ext}").is_file():
                            return True
                    if is_package_dir(entry / module_name):
                        return True
        except Exception:
            pass

    return False


def is_stdlib_module(module_name: str) -> bool:
    """Check if the module is part of Python's standard library."""
    if hasattr(sys, "stdlib_module_names"):
        return module_name in sys.stdlib_module_names
    return module_name in sys.builtin_module_names


def is_installed_package(module_name: str) -> bool:
    """Check if a module is installed in the active Python environment."""
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            return True
    except Exception:
        pass

    try:
        dist_map = importlib.metadata.packages_distributions()
        if module_name in dist_map:
            return True
    except Exception:
        pass

    return False


def get_distribution_name(module_name: str) -> str:
    """Map top-level import name to its standard PyPI distribution name if different."""
    known_mappings = {
        "PIL": "pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "bs4": "beautifulsoup4",
        "yaml": "PyYAML",
        "dotenv": "python-dotenv",
        "dateutil": "python-dateutil",
        "serial": "pyserial",
        "jwt": "PyJWT",
        "jose": "python-jose",
        "magic": "python-magic",
        "fitz": "PyMuPDF",
        "docx": "python-docx",
        "pptx": "python-pptx",
        "git": "GitPython",
        "github": "PyGithub",
        "websocket": "websocket-client",
        "OpenGL": "PyOpenGL",
        "attr": "attrs",
    }
    return known_mappings.get(module_name, module_name)


def find_missing_installed_imports(project_path: Path) -> List[Tuple[str, Path, int]]:
    """Identify third-party imports in project code that are not installed in the active environment."""
    imports, _ = scan_project_ast(project_path)
    missing: List[Tuple[str, Path, int]] = []
    checked: Set[str] = set()

    for item in imports:
        mod = item.module_name
        if mod in checked:
            continue
        if is_stdlib_module(mod) or is_local_module(mod, project_path, item.file_path):
            continue

        checked.add(mod)
        if not is_installed_package(mod):
            missing.append((mod, item.file_path, item.line_number))

    return missing
