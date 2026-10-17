"""Tests for core DevDoctor models."""

from pathlib import Path
from devdoctor.models import (
    Confidence,
    Diagnostic,
    DiagnosticReport,
    FixAction,
    ProjectInfo,
    ScanContext,
    Severity,
)


def test_diagnostic_properties():
    diag_ok = Diagnostic(title="Python 3.12", severity=Severity.OK)
    assert diag_ok.is_ok
    assert not diag_ok.is_problem
    assert not diag_ok.is_error

    diag_warn = Diagnostic(title="Port 8000", severity=Severity.WARNING)
    assert diag_warn.is_warning
    assert diag_warn.is_problem
    assert not diag_warn.is_error

    diag_err = Diagnostic(title="Virtual environment", severity=Severity.ERROR)
    assert diag_err.is_error
    assert diag_err.is_problem


def test_diagnostic_report_score_calculation(tmp_path: Path):
    proj_info = ProjectInfo(root=tmp_path, name="test")

    # 1. Zero problems -> 100/100
    report_clean = DiagnosticReport(
        project_path=tmp_path,
        project_info=proj_info,
        diagnostics=[
            Diagnostic(title="Python 3.12", severity=Severity.OK),
            Diagnostic(title="pip 25.0", severity=Severity.OK),
        ],
    )
    assert report_clean.score == 100
    assert report_clean.is_healthy
    assert report_clean.total_problems == 0

    # 2. 2 errors + 1 warning -> 100 - (2*12 + 1*4) = 72
    report_problems = DiagnosticReport(
        project_path=tmp_path,
        project_info=proj_info,
        diagnostics=[
            Diagnostic(title="Python 3.12", severity=Severity.OK),
            Diagnostic(title="pip 25.0", severity=Severity.OK),
            Diagnostic(title="Git 2.51", severity=Severity.OK),
            Diagnostic(title="Docker 28.4", severity=Severity.OK),
            Diagnostic(title="Virtualenv", severity=Severity.ERROR),
            Diagnostic(title="Env var", severity=Severity.ERROR),
            Diagnostic(title="Port 8000", severity=Severity.WARNING),
        ],
    )
    assert report_problems.score == 72
    assert not report_problems.is_healthy
    assert report_problems.total_problems == 3
    assert len(report_problems.passed) == 4
    assert len(report_problems.errors) == 2
    assert len(report_problems.warnings) == 1


def test_fix_action_file_create_and_append(tmp_path: Path):
    target = tmp_path / "subdir" / ".env"
    ctx = ScanContext(project_path=tmp_path)

    # File create
    action_create = FixAction(
        description="Create .env",
        action_type="file_create",
        target_path=target,
        content="DEBUG=True\n",
        safe=True,
    )
    assert action_create.execute(ctx)
    assert target.exists()
    assert "DEBUG=True" in target.read_text(encoding="utf-8")

    # File append
    action_append = FixAction(
        description="Add DATABASE_URL",
        action_type="file_append",
        target_path=target,
        content="DATABASE_URL=postgres://localhost/db",
        safe=True,
    )
    assert action_append.execute(ctx)
    content = target.read_text(encoding="utf-8")
    assert "DATABASE_URL=postgres://localhost/db" in content
    assert "DEBUG=True" in content


def test_fix_action_custom_handler(tmp_path: Path):
    ctx = ScanContext(project_path=tmp_path)
    called = []

    def handler(c: ScanContext) -> bool:
        called.append(c.project_path)
        return True

    action = FixAction(description="Custom fix", handler=handler)
    assert action.execute(ctx)
    assert called == [tmp_path]
