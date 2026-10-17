"""Tests for DevDoctor CLI interface."""

from pathlib import Path
from devdoctor.cli import main


def test_cli_scan_default(tmp_path: Path, capsys):
    ret = main(["scan", str(tmp_path)])
    assert ret in (0, 1)


def test_cli_scan_json(tmp_path: Path, capsys):
    ret = main(["scan", str(tmp_path), "--json"])
    assert ret in (0, 1)
    captured = capsys.readouterr()
    assert '"version": "0.1.0"' in captured.out
    assert '"score":' in captured.out


def test_cli_project(tmp_path: Path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'myapp'\n", encoding="utf-8")
    ret = main(["project", str(tmp_path)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Project Profile:" in captured.out


def test_cli_dependencies(tmp_path: Path, capsys):
    ret = main(["dependencies", str(tmp_path)])
    assert ret in (0, 1)
    captured = capsys.readouterr()
    assert "DevDoctor Dependency Diagnostics" in captured.out


def test_cli_fix_dry_run(tmp_path: Path, capsys):
    ret = main(["fix", str(tmp_path), "--dry-run"])
    assert ret in (0, 1)


def test_cli_report_markdown(tmp_path: Path, capsys):
    out_file = tmp_path / "diagnostic_report.md"
    ret = main(["report", str(tmp_path), "--format", "markdown", "-o", str(out_file)])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# DevDoctor Diagnostic Report" in content
