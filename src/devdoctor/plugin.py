"""Plugin discovery and check extension loader."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
from pathlib import Path
from typing import List, Optional

from devdoctor.checks import get_registered_checks
from devdoctor.checks.base import Check, register_check

logger = logging.getLogger("devdoctor.plugins")


def load_entrypoint_checks() -> List[Check]:
    """Discover checks registered via Python packaging entry-points ('devdoctor.checks')."""
    discovered: List[Check] = []
    try:
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            check_eps = eps.select(group="devdoctor.checks")
        else:
            check_eps = eps.get("devdoctor.checks", [])

        for ep in check_eps:
            try:
                obj = ep.load()
                if isinstance(obj, type) and issubclass(obj, Check):
                    register_check(obj)
                    discovered.append(obj())
                elif callable(obj):
                    # Check factory
                    inst = obj()
                    if isinstance(inst, Check):
                        discovered.append(inst)
            except Exception as e:
                logger.debug(f"Failed to load entry point {ep.name}: {e}")
    except Exception as e:
        logger.debug(f"Error querying entry points: {e}")

    return discovered


def load_local_checks(checks_dir: Path) -> List[Check]:
    """Load custom check modules from a local directory (e.g. .devdoctor/checks/*.py)."""
    custom_checks: List[Check] = []
    if not checks_dir.is_dir():
        return custom_checks

    for py_file in checks_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"devdoctor_local_{py_file.stem}", py_file)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for attr_name in dir(mod):
                    val = getattr(mod, attr_name)
                    if isinstance(val, type) and issubclass(val, Check) and val is not Check:
                        register_check(val)
                        custom_checks.append(val())
        except Exception as e:
            logger.debug(f"Failed to load local check from {py_file}: {e}")

    return custom_checks


def discover_all_checks(project_path: Optional[Path] = None, custom_dir: Optional[Path] = None) -> List[Check]:
    """Collect all builtin, entrypoint, and local directory checks."""
    # 1. Built-in checks
    all_checks = list(get_registered_checks())

    # 2. Package entry points
    load_entrypoint_checks()

    # 3. Project-local .devdoctor/checks/
    if project_path:
        local_dir = project_path / ".devdoctor" / "checks"
        if local_dir.is_dir():
            load_local_checks(local_dir)

    # 4. Explicit custom directory if provided
    if custom_dir and custom_dir.is_dir():
        load_local_checks(custom_dir)

    return get_registered_checks()
