"""Tests for environment file parsing and AST source scanning."""

from pathlib import Path
from devdoctor.utils.ast_imports import find_missing_installed_imports, scan_project_ast
from devdoctor.utils.env_parser import find_missing_env_keys, parse_env_content, parse_env_file


def test_parse_env_content():
    content = """
    # Database config
    export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
    PORT=8000 # inline comment
    DEBUG=True
    EMPTY=
    """
    parsed = parse_env_content(content)
    assert parsed["DATABASE_URL"] == "postgresql://user:pass@localhost:5432/mydb"
    assert parsed["PORT"] == "8000"
    assert parsed["DEBUG"] == "True"
    assert parsed["EMPTY"] == ""


def test_find_missing_env_keys(tmp_path: Path):
    example = tmp_path / ".env.example"
    actual = tmp_path / ".env"

    example.write_text("DATABASE_URL=\nSECRET_KEY=\nREDIS_URL=\n", encoding="utf-8")
    actual.write_text("DATABASE_URL=postgres://localhost/db\n", encoding="utf-8")

    missing = find_missing_env_keys(example, actual)
    assert missing == ["REDIS_URL", "SECRET_KEY"]


def test_ast_scan_imports_and_env_vars(tmp_path: Path):
    code_file = tmp_path / "app.py"
    code_file.write_text(
        """
import os
import math
from devdoctor import models

db_url = os.environ["DATABASE_URL"]
api_key = os.getenv("API_KEY")
debug = os.getenv("DEBUG", "False")
        """,
        encoding="utf-8",
    )

    imports, env_vars = scan_project_ast(tmp_path)
    import_mods = [i.module_name for i in imports]
    assert "os" in import_mods
    assert "math" in import_mods
    assert "devdoctor" in import_mods

    env_names = [e.var_name for e in env_vars]
    assert "DATABASE_URL" in env_names
    assert "API_KEY" in env_names
    assert "DEBUG" in env_names

    db_entry = next(e for e in env_vars if e.var_name == "DATABASE_URL")
    assert db_entry.is_required
    assert not db_entry.has_default

    debug_entry = next(e for e in env_vars if e.var_name == "DEBUG")
    assert debug_entry.has_default
