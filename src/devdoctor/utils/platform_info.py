"""Platform and Python environment helper utilities."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Optional, Tuple


def is_windows() -> bool:
    """Return True if running on Windows."""
    return sys.platform.startswith("win") or platform.system() == "Windows"


def is_macos() -> bool:
    """Return True if running on macOS."""
    return sys.platform == "darwin" or platform.system() == "Darwin"


def is_linux() -> bool:
    """Return True if running on Linux."""
    return sys.platform.startswith("linux") or platform.system() == "Linux"


def is_in_virtualenv() -> bool:
    """Deterministically check if current Python is running inside a virtual environment.
    
    Checks both sys.prefix != sys.base_prefix (standard Python 3.3+ venv behavior)
    and common environment variables like VIRTUAL_ENV or CONDA_PREFIX.
    """
    has_base = hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix
    has_real = hasattr(sys, "real_prefix")  # old virtualenv
    has_env = bool(os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX"))
    return has_base or has_real or has_env


def find_local_venv(project_path: Path) -> Optional[Path]:
    """Look for standard virtualenv directories in the project root (.venv, venv, env)."""
    candidates = [".venv", "venv", "env", ".env_dir"]
    for name in candidates:
        candidate = project_path / name
        # Check for scripts/bin inside candidate
        if candidate.is_dir():
            if is_windows() and (candidate / "Scripts" / "python.exe").exists():
                return candidate
            elif (candidate / "bin" / "python").exists():
                return candidate
            elif (candidate / "pyvenv.cfg").exists():
                return candidate
    return None


def get_venv_activation_command(venv_dir: Path | str = ".venv") -> str:
    """Return the platform-specific shell command to activate the virtualenv."""
    venv_path = Path(venv_dir)
    if is_windows():
        return f"{venv_path}\\Scripts\\activate"
    return f"source {venv_path}/bin/activate"


def get_python_version_tuple() -> Tuple[int, int, int]:
    """Return Python version as a tuple of (major, minor, micro)."""
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def get_python_version_str() -> str:
    """Return Python version as 'X.Y.Z'."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
