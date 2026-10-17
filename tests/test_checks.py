"""Tests for all built-in DevDoctor diagnostic checks."""

from pathlib import Path
from devdoctor.checks.dependencies import DependencyConflictsCheck
from devdoctor.checks.django import DjangoCheck
from devdoctor.checks.docker import DockerCheck
from devdoctor.checks.environment import EnvironmentCheck
from devdoctor.checks.fastapi import FastAPICheck
from devdoctor.checks.filesystem import FilesystemCheck
from devdoctor.checks.git import GitCheck
from devdoctor.checks.imports import BrokenImportsCheck
from devdoctor.checks.pip import PipAvailabilityCheck
from devdoctor.checks.ports import PortConflictsCheck
from devdoctor.checks.postgres import PostgresCheck
from devdoctor.checks.python import PythonVersionCheck
from devdoctor.checks.redis import RedisCheck
from devdoctor.checks.virtualenv import VirtualenvCheck
from devdoctor.models import ProjectInfo, ScanContext, Severity


def test_python_version_check_compatible(tmp_path: Path):
    chk = PythonVersionCheck()
    ctx = ScanContext(project_path=tmp_path)
    res = chk.run(ctx)
    assert res.is_ok
    assert "Python" in res.title


def test_python_version_check_incompatible(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('requires-python = ">=3.99"\n', encoding="utf-8")
    chk = PythonVersionCheck()
    ctx = ScanContext(project_path=tmp_path)
    res = chk.run(ctx)
    assert res.is_error
    assert "incompatible" in res.title.lower()


def test_pip_availability_check(tmp_path: Path):
    chk = PipAvailabilityCheck()
    ctx = ScanContext(project_path=tmp_path)
    res = chk.run(ctx)
    assert res.is_ok
    assert "pip" in res.title


def test_virtualenv_check(tmp_path: Path):
    chk = VirtualenvCheck()
    ctx = ScanContext(project_path=tmp_path)
    res = chk.run(ctx)
    # Since we are running in tests, either ok (if venv) or error
    assert res.severity in (Severity.OK, Severity.ERROR)
    if res.is_error:
        assert "virtual environment" in res.title.lower()
        assert res.fix is not None


def test_git_check_and_gitignore_env(tmp_path: Path):
    chk = GitCheck()
    # Create git repo mock
    (tmp_path / ".git").mkdir()
    (tmp_path / ".env").write_text("SECRET=123\n", encoding="utf-8")

    ctx = ScanContext(project_path=tmp_path)
    results = chk.run(ctx)

    # Should detect .env not ignored
    err = next((d for d in results if "not ignored" in d.title.lower()), None)
    assert err is not None
    assert err.severity == Severity.ERROR
    assert err.fix_action is not None
    assert err.fix_action.safe


def test_environment_check_missing_example(tmp_path: Path):
    (tmp_path / ".env.example").write_text("DATABASE_URL=\nAPI_KEY=\n", encoding="utf-8")
    chk = EnvironmentCheck()
    ctx = ScanContext(project_path=tmp_path)
    results = chk.run(ctx)

    err = next((d for d in results if "missing" in d.title.lower()), None)
    assert err is not None
    assert err.severity == Severity.ERROR


def test_environment_check_missing_required_in_code(tmp_path: Path):
    code = tmp_path / "settings.py"
    code.write_text('import os\nDATABASE_URL = os.environ["DATABASE_URL"]\n', encoding="utf-8")
    chk = EnvironmentCheck()
    ctx = ScanContext(project_path=tmp_path)
    results = chk.run(ctx)

    err = next((d for d in results if "DATABASE_URL" in d.message), None)
    assert err is not None
    assert err.severity == Severity.ERROR
    assert "settings.py" in err.evidence


def test_broken_imports_check(tmp_path: Path):
    code = tmp_path / "foo.py"
    code.write_text("import totally_fake_nonexistent_package_xyz_999\n", encoding="utf-8")
    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    results = chk.run(ctx)

    err = next((d for d in results if "totally_fake_nonexistent_package_xyz_999" in d.title), None)
    assert err is not None
    assert err.severity == Severity.ERROR
    assert "pip install" in err.command


def test_django_check(tmp_path: Path):
    (tmp_path / "manage.py").write_text("# Django manage.py", encoding="utf-8")
    settings = tmp_path / "settings.py"
    settings.write_text(
        'DEBUG = True\nSECRET_KEY = "django-insecure-test"\nALLOWED_HOSTS = []\n',
        encoding="utf-8",
    )

    chk = DjangoCheck()
    proj = ProjectInfo(root=tmp_path, frameworks=["Django"])
    ctx = ScanContext(project_path=tmp_path, project_info=proj)
    results = chk.run(ctx)

    titles = [d.title for d in results]
    assert any("DEBUG is True" in t for t in titles)
    assert any("SECRET_KEY" in t for t in titles)
    assert any("ALLOWED_HOSTS" in t for t in titles)


def test_fastapi_check(tmp_path: Path):
    chk = FastAPICheck()
    proj = ProjectInfo(root=tmp_path, frameworks=["FastAPI"])
    ctx = ScanContext(project_path=tmp_path, project_info=proj)
    results = chk.run(ctx)
    assert len(results) >= 2  # uvicorn check + port 8000 check
