"""Parsing utilities for .env and .env.example files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Set


def parse_env_content(content: str) -> Dict[str, str]:
    """Parse .env formatted text into key-value pairs."""
    result: Dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Support 'export KEY=VAL'
        if line.startswith("export "):
            line = line[len("export "):].strip()

        # Match KEY=VALUE or KEY="VALUE" or KEY='VALUE'
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if match:
            key = match.group(1).strip()
            val = match.group(2).strip()
            # Unquote if enclosed in matching quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            else:
                # Strip inline comments: KEY=foo # comment
                val = re.sub(r"\s+#.*$", "", val).strip()
            result[key] = val
    return result


def parse_env_file(file_path: Path) -> Dict[str, str]:
    """Read and parse a .env file."""
    if not file_path.is_file():
        return {}
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return parse_env_content(content)
    except Exception:
        return {}


def get_env_keys(file_path: Path) -> Set[str]:
    """Return all defined keys in an environment file."""
    return set(parse_env_file(file_path).keys())


def find_missing_env_keys(example_file: Path, target_env_file: Path) -> List[str]:
    """Compare keys in .env.example against .env and return missing keys."""
    example_keys = get_env_keys(example_file)
    target_keys = get_env_keys(target_env_file)
    missing = example_keys - target_keys
    return sorted(list(missing))
