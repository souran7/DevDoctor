"""Tests for DevDoctor fix engine and safe remediation."""

from pathlib import Path
from devdoctor.fixer import Fixer
from devdoctor.models import Diagnostic, DiagnosticReport, FixAction, ProjectInfo, ScanContext, Severity


def test_fixer_plan_building(tmp_path: Path):
    target_env = tmp_path / ".env"
    safe_action = FixAction(
        description="Create .env",
        safe=True,
        action_type="file_create",
        target_path=target_env,
        content="DEBUG=True\n",
    )
    action_required = FixAction(
        description="Free port 8000",
        safe=False,
        command="devdoctor port free 8000",
    )

    report = DiagnosticReport(
        project_path=tmp_path,
        project_info=ProjectInfo(root=tmp_path),
        diagnostics=[
            Diagnostic(title="Safe issue", severity=Severity.ERROR, fix_action=safe_action),
            Diagnostic(title="Port issue", severity=Severity.WARNING, fix_action=action_required),
        ],
    )

    fixer = Fixer()
    plan = fixer.build_plan(report)
    assert plan.total_count == 2
    assert len(plan.safe_items) == 1
    assert len(plan.action_items) == 1
    assert plan.safe_items[0].is_safe
    assert not plan.action_items[0].is_safe


def test_fixer_execute_safe_only(tmp_path: Path):
    target = tmp_path / ".env"
    safe_action = FixAction(
        description="Create .env",
        safe=True,
        action_type="file_create",
        target_path=target,
        content="CREATED=1\n",
    )
    report = DiagnosticReport(
        project_path=tmp_path,
        project_info=ProjectInfo(root=tmp_path),
        diagnostics=[
            Diagnostic(title="Missing .env", severity=Severity.ERROR, fix_action=safe_action),
        ],
    )

    fixer = Fixer()
    plan = fixer.build_plan(report)
    ctx = ScanContext(project_path=tmp_path)

    res = fixer.execute_plan(plan, ctx, safe_only=True, interactive=False)
    assert len(res.applied) == 1
    assert target.exists()
    assert "CREATED=1" in target.read_text(encoding="utf-8")


def test_fixer_dry_run(tmp_path: Path):
    target = tmp_path / "should_not_exist.txt"
    safe_action = FixAction(
        description="Create test file",
        safe=True,
        action_type="file_create",
        target_path=target,
        content="test",
    )
    report = DiagnosticReport(
        project_path=tmp_path,
        project_info=ProjectInfo(root=tmp_path),
        diagnostics=[Diagnostic(title="Test", severity=Severity.ERROR, fix_action=safe_action)],
    )

    fixer = Fixer()
    plan = fixer.build_plan(report)
    ctx = ScanContext(project_path=tmp_path)

    res = fixer.execute_plan(plan, ctx, dry_run=True)
    assert len(res.applied) == 0
    assert not target.exists()
