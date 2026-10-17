from devdoctor._version import __version__
from devdoctor.api import DevDoctor
from devdoctor.checks.base import Check, check, get_registered_checks, register_check
from devdoctor.fixer import FixAction, FixPlan, FixResult, Fixer
from devdoctor.models import (
    Confidence,
    Diagnostic,
    DiagnosticReport,
    ProjectInfo,
    ScanContext,
    Severity,
)
from devdoctor.project import detect_project
from devdoctor.reporter import Reporter
from devdoctor.scanner import Scanner

__all__ = [
    "DevDoctor",
    "Diagnostic",
    "DiagnosticReport",
    "FixAction",
    "FixPlan",
    "FixResult",
    "Fixer",
    "ProjectInfo",
    "ScanContext",
    "Severity",
    "Confidence",
    "Check",
    "check",
    "register_check",
    "get_registered_checks",
    "detect_project",
    "Reporter",
    "Scanner",
    "__version__",
]
