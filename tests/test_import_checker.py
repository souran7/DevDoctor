"""Regression tests for DevDoctor's import detection and namespace package handling."""

from pathlib import Path
from devdoctor.checks.imports import BrokenImportsCheck
from devdoctor.models import ScanContext, Severity
from devdoctor.utils.ast_imports import (
    find_missing_installed_imports,
    get_distribution_name,
    is_installed_package,
    is_local_module,
)


def test_a_local_namespace_packages(tmp_path: Path):
    """Test A — Local namespace packages:
    Create a project with core/, ui/, and utils/ without __init__.py.
    Verify that importing these local namespace packages is NOT reported as missing dependencies.
    """
    # Create structure:
    # project/
    # ├── app.py
    # ├── core/
    # │   └── example.py
    # ├── ui/
    # │   └── example.py
    # └── utils/
    #     └── example.py
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "example.py").write_text("def run_core(): pass\n", encoding="utf-8")

    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "example.py").write_text("def run_ui(): pass\n", encoding="utf-8")

    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "example.py").write_text("def run_utils(): pass\n", encoding="utf-8")

    app_py = tmp_path / "app.py"
    app_py.write_text(
        """
import core
from core import example as core_example
import ui
from ui.example import run_ui
import utils
from utils import example as utils_example
""",
        encoding="utf-8",
    )

    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    diagnostics = chk.run(ctx)

    # None of core, ui, utils should be flagged as missing
    flagged = [d.metadata.get("module") for d in diagnostics]
    assert "core" not in flagged
    assert "ui" not in flagged
    assert "utils" not in flagged
    assert len(diagnostics) == 0


def test_b_local_regular_packages(tmp_path: Path):
    """Test B — Local regular packages:
    Verify that local packages with __init__.py are recognized as local packages.
    """
    pkg_dir = tmp_path / "mypackage"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("# regular package\n", encoding="utf-8")
    (pkg_dir / "service.py").write_text("def serve(): pass\n", encoding="utf-8")

    (tmp_path / "main.py").write_text("import mypackage\nfrom mypackage import service\n", encoding="utf-8")

    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    diagnostics = chk.run(ctx)

    flagged = [d.metadata.get("module") for d in diagnostics]
    assert "mypackage" not in flagged
    assert len(diagnostics) == 0


def test_c_genuine_missing_dependency(tmp_path: Path):
    """Test C — Genuine missing dependency:
    Import a deliberately nonexistent third-party module and verify DevDoctor reports it appropriately.
    """
    (tmp_path / "app.py").write_text("import deliberately_nonexistent_pypi_pkg_98765\n", encoding="utf-8")

    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    diagnostics = chk.run(ctx)

    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.severity == Severity.ERROR
    assert "deliberately_nonexistent_pypi_pkg_98765" in diag.title
    assert "pip install deliberately_nonexistent_pypi_pkg_98765" in diag.command


def test_d_installed_third_party_dependency(tmp_path: Path):
    """Test D — Installed third-party dependency:
    Verify that a dependency installed in the active environment (e.g. rich, packaging) is not reported as missing.
    """
    (tmp_path / "app.py").write_text("import rich\nimport packaging\n", encoding="utf-8")

    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    diagnostics = chk.run(ctx)

    assert len(diagnostics) == 0


def test_e_nested_local_imports(tmp_path: Path):
    """Test E — Nested local imports:
    Verify that modules and subpackages in nested project directories are handled correctly.
    """
    # project/
    # ├── app.py
    # └── core/
    #     ├── tracker.py
    #     └── detector/
    #         └── model.py
    core_dir = tmp_path / "core"
    detector_dir = core_dir / "detector"
    detector_dir.mkdir(parents=True)

    (detector_dir / "model.py").write_text("class Model: pass\n", encoding="utf-8")
    (core_dir / "tracker.py").write_text("from detector.model import Model\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("from core.detector import model\nimport core.tracker\n", encoding="utf-8")

    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    diagnostics = chk.run(ctx)

    flagged = [d.metadata.get("module") for d in diagnostics]
    assert "core" not in flagged
    assert "detector" not in flagged
    assert len(diagnostics) == 0


def test_f_src_layout(tmp_path: Path):
    """Test F — src/ layout:
    Verify that modules under the project's src/ directory are recognized.
    """
    # project/
    # ├── pyproject.toml
    # └── src/
    #     └── myproject/
    #         ├── engine.py
    #         └── worker.py
    src_pkg = tmp_path / "src" / "myproject"
    src_pkg.mkdir(parents=True)

    (src_pkg / "engine.py").write_text("def start_engine(): pass\n", encoding="utf-8")
    (src_pkg / "worker.py").write_text("from myproject.engine import start_engine\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("import myproject.worker\n", encoding="utf-8")

    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    diagnostics = chk.run(ctx)

    flagged = [d.metadata.get("module") for d in diagnostics]
    assert "myproject" not in flagged
    assert len(diagnostics) == 0


def test_arbitrary_directory_not_treated_as_package(tmp_path: Path):
    """Verify that arbitrary non-Python directories (e.g. templates/ with only html)
    are NOT treated as local packages.
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "index.html").write_text("<h1>Hello</h1>\n", encoding="utf-8")

    (tmp_path / "app.py").write_text("import templates\n", encoding="utf-8")

    # templates should not be considered a local package because it contains no Python files
    assert not is_local_module("templates", tmp_path)

    chk = BrokenImportsCheck()
    ctx = ScanContext(project_path=tmp_path)
    diagnostics = chk.run(ctx)
    assert any("templates" in d.title for d in diagnostics)


def test_distribution_name_mapping():
    """Verify that known import names map to their correct PyPI distribution names."""
    assert get_distribution_name("PIL") == "pillow"
    assert get_distribution_name("cv2") == "opencv-python"
    assert get_distribution_name("yaml") == "PyYAML"
    assert get_distribution_name("sklearn") == "scikit-learn"
    assert get_distribution_name("unknown_pkg") == "unknown_pkg"
