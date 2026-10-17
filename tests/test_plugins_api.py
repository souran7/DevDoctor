"""Tests for plugin architecture, @check decorator, and Python API."""

from pathlib import Path
from devdoctor import DevDoctor, Diagnostic, ScanContext, Severity, check


def test_custom_check_decorator(tmp_path: Path):
    @check("test_custom_service", title="Test Custom Service", category="custom")
    def run_custom(ctx: ScanContext):
        return Diagnostic(
            title="Custom Check Passed",
            severity=Severity.OK,
            message="Custom service is operating normally.",
        )

    doctor = DevDoctor(project_path=tmp_path)
    report = doctor.scan(check_names=["test_custom_service"])
    assert any(d.title == "Custom Check Passed" for d in report.diagnostics)


def test_devdoctor_api_detect_and_scan(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    doctor = DevDoctor(project_path=tmp_path)

    info = doctor.detect_project()
    assert info.name == tmp_path.name

    report = doctor.scan()
    assert report.score >= 0
    assert report.project_path == tmp_path.resolve()
