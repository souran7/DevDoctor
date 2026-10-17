"""Project detector: inspects files and config to determine project type and tech stack."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from devdoctor.models import ProjectInfo


def parse_requirements_txt(file_path: Path) -> Dict[str, str]:
    """Extract package names and version specifiers from a requirements.txt file."""
    deps: Dict[str, str] = {}
    if not file_path.is_file():
        return deps
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Match package name and optional version specifier
            match = re.match(r"^([A-Za-z0-9_.\-]+)\s*([<>=!~].*)?$", line)
            if match:
                pkg = match.group(1).lower().replace("_", "-")
                spec = match.group(2).strip() if match.group(2) else "*"
                deps[pkg] = spec
    except Exception:
        pass
    return deps


def parse_pyproject_deps(file_path: Path) -> Dict[str, str]:
    """Parse dependencies from pyproject.toml."""
    deps: Dict[str, str] = {}
    if not file_path.is_file():
        return deps
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        # Match standard PEP 621 dependencies list: dependencies = [ ... ]
        in_deps = False
        for line in content.splitlines():
            line = line.strip()
            if re.match(r"^dependencies\s*=\s*\[", line):
                in_deps = True
                continue
            if in_deps:
                if line.startswith("]"):
                    in_deps = False
                    continue
                # Match quoted string like "fastapi>=0.100.0"
                match = re.search(r'["\']([A-Za-z0-9_.\-]+)([^"\']*)["\']', line)
                if match:
                    pkg = match.group(1).lower().replace("_", "-")
                    spec = match.group(2).strip() or "*"
                    deps[pkg] = spec
    except Exception:
        pass
    return deps


def detect_project(project_path: Path) -> ProjectInfo:
    """Analyze the project directory and build a deterministic ProjectInfo profile."""
    root = project_path.resolve()
    name = root.name

    config_files: List[str] = []
    technologies: List[str] = ["Python"]
    frameworks: List[str] = []
    project_type: Optional[str] = None
    dependencies: Dict[str, str] = {}

    # Check key files
    known_files = [
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "manage.py",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yaml",
        "compose.yml",
        ".env",
        ".env.example",
        ".git",
        "alembic.ini",
        "package.json",
        "Pipfile",
        "poetry.lock",
    ]

    for fname in known_files:
        if (root / fname).exists():
            config_files.append(fname)

    # Collect dependencies
    if (root / "requirements.txt").exists():
        dependencies.update(parse_requirements_txt(root / "requirements.txt"))
    if (root / "pyproject.toml").exists():
        dependencies.update(parse_pyproject_deps(root / "pyproject.toml"))

    dep_keys = set(dependencies.keys())

    # Detect Django
    if (root / "manage.py").exists() or "django" in dep_keys:
        project_type = "Django"
        frameworks.append("Django")
        if "Django" not in technologies:
            technologies.append("Django")

    # Detect FastAPI
    elif "fastapi" in dep_keys:
        project_type = "FastAPI"
        frameworks.append("FastAPI")
        if "FastAPI" not in technologies:
            technologies.append("FastAPI")

    # Detect Flask
    elif "flask" in dep_keys:
        project_type = "Flask"
        frameworks.append("Flask")
        if "Flask" not in technologies:
            technologies.append("Flask")

    # Check AST or code if not found via dependencies
    if not project_type:
        for py_file in ["main.py", "app.py", "api.py", "server.py"]:
            candidate = root / py_file
            if candidate.is_file():
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                    if "FastAPI(" in text or "from fastapi import" in text:
                        project_type = "FastAPI"
                        frameworks.append("FastAPI")
                        if "FastAPI" not in technologies:
                            technologies.append("FastAPI")
                        break
                    elif "Flask(" in text or "from flask import" in text:
                        project_type = "Flask"
                        frameworks.append("Flask")
                        if "Flask" not in technologies:
                            technologies.append("Flask")
                        break
                except Exception:
                    pass

    if not project_type:
        project_type = "Generic Python"

    # Detect Docker
    has_docker = (
        (root / "Dockerfile").exists()
        or (root / "docker-compose.yml").exists()
        or (root / "docker-compose.yaml").exists()
        or (root / "compose.yaml").exists()
        or (root / "compose.yml").exists()
    )
    if has_docker:
        technologies.append("Docker")

    # Detect Compose contents for database and cache services
    compose_content = ""
    for cfile in ["docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"]:
        target = root / cfile
        if target.is_file():
            try:
                compose_content += "\n" + target.read_text(encoding="utf-8", errors="replace").lower()
            except Exception:
                pass

    # Read .env if present
    env_content = ""
    if (root / ".env").is_file():
        try:
            env_content = (root / ".env").read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            pass

    # Detect PostgreSQL
    if (
        "postgres" in compose_content
        or "psql" in compose_content
        or "psycopg" in dep_keys
        or "psycopg2" in dep_keys
        or "psycopg2-binary" in dep_keys
        or "asyncpg" in dep_keys
        or "postgresql://" in env_content
        or "postgres://" in env_content
    ):
        technologies.append("PostgreSQL")

    # Detect Redis
    if (
        "redis" in compose_content
        or "redis" in dep_keys
        or "redis://" in env_content
    ):
        technologies.append("Redis")

    # Detect Celery
    if "celery" in dep_keys or "celery" in compose_content:
        technologies.append("Celery")

    # Detect Alembic
    if (root / "alembic.ini").exists() or "alembic" in dep_keys:
        technologies.append("Alembic")

    # Detect Node.js
    if (root / "package.json").exists():
        technologies.append("Node.js")

    return ProjectInfo(
        root=root,
        name=name,
        project_type=project_type,
        technologies=technologies,
        frameworks=frameworks,
        config_files=config_files,
        dependencies=dependencies,
    )
