"""Base Check interface and check decorator for DevDoctor."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type, Union

from devdoctor.models import Diagnostic, ScanContext


class Check:
    """Base class for all DevDoctor diagnostic checks."""
    name: str = "base"
    title: str = "Base Check"
    description: str = ""
    category: str = "system"  # system, environment, git, network, dependencies, framework, filesystem
    enabled: bool = True

    def run(self, context: ScanContext) -> Union[Diagnostic, List[Diagnostic], None]:
        """Execute the check and return one or more Diagnostics."""
        raise NotImplementedError("Subclasses must implement run(context)")


_GLOBAL_CHECK_REGISTRY: Dict[str, Type[Check]] = {}


def register_check(check_cls: Type[Check]) -> Type[Check]:
    """Register a Check class in the global registry."""
    if hasattr(check_cls, "name") and check_cls.name:
        _GLOBAL_CHECK_REGISTRY[check_cls.name] = check_cls
    return check_cls


def get_registered_checks() -> List[Check]:
    """Return instantiated instances of all registered checks."""
    return [cls() for cls in _GLOBAL_CHECK_REGISTRY.values() if cls.enabled]


def check(
    name: str,
    title: Optional[str] = None,
    category: str = "custom",
    description: str = "",
) -> Callable[[Callable[[ScanContext], Any]], Type[Check]]:
    """Decorator to convert a simple function into a registered DevDoctor Check.
    
    Example:
        @check("my_api", title="My API Check")
        def check_my_api(context: ScanContext) -> Diagnostic | None:
            ...
    """
    def decorator(fn: Callable[[ScanContext], Any]) -> Type[Check]:
        check_name = name
        check_title = title or name.replace("_", " ").title()
        check_category = category
        check_desc = description or (fn.__doc__ or "")

        class FunctionalCheck(Check):
            def run(self, context: ScanContext) -> Any:
                return fn(context)

        FunctionalCheck.name = check_name
        FunctionalCheck.title = check_title
        FunctionalCheck.category = check_category
        FunctionalCheck.description = check_desc

        register_check(FunctionalCheck)
        return FunctionalCheck

    return decorator
