"""Tests for project detection and tech stack analysis."""

from pathlib import Path
from devdoctor.project import detect_project, parse_pyproject_deps, parse_requirements_txt


def test_detect_django_project(tmp_path: Path):
    (tmp_path / "manage.py").write_text("# Django manage.py", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("django>=4.2\npsycopg2-binary\n", encoding="utf-8")

    info = detect_project(tmp_path)
    assert info.project_type == "Django"
    assert "Django" in info.frameworks
    assert "PostgreSQL" in info.technologies
    assert "django" in info.dependencies
    assert "manage.py" in info.config_files


def test_detect_fastapi_docker_redis(tmp_path: Path):
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  redis:\n    image: redis:alpine\n    ports:\n      - 6379:6379\n",
        encoding="utf-8",
    )

    info = detect_project(tmp_path)
    assert info.project_type == "FastAPI"
    assert "FastAPI" in info.frameworks
    assert "Docker" in info.technologies
    assert "Redis" in info.technologies
    assert "Dockerfile" in info.config_files
    assert "docker-compose.yml" in info.config_files
    assert "FastAPI + Docker + Redis" in info.summary_stack


def test_parse_requirements_txt(tmp_path: Path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text(
        "# Comment\nfastapi>=0.110.0\npydantic<3.0\nrequests\n-r other.txt\n",
        encoding="utf-8",
    )
    deps = parse_requirements_txt(req_file)
    assert deps["fastapi"] == ">=0.110.0"
    assert deps["pydantic"] == "<3.0"
    assert deps["requests"] == "*"
