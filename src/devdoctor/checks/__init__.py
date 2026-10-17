"""DevDoctor built-in diagnostic checks."""

from devdoctor.checks.base import Check, check, get_registered_checks, register_check
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

__all__ = [
    "Check",
    "check",
    "register_check",
    "get_registered_checks",
    "PythonVersionCheck",
    "PipAvailabilityCheck",
    "VirtualenvCheck",
    "GitCheck",
    "EnvironmentCheck",
    "PortConflictsCheck",
    "FilesystemCheck",
    "BrokenImportsCheck",
    "DependencyConflictsCheck",
    "DjangoCheck",
    "FastAPICheck",
    "DockerCheck",
    "PostgresCheck",
    "RedisCheck",
]
