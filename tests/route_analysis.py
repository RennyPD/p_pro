"""Static call-graph helpers for the route guard tests (audit and locks).

``reaches(function, targets)`` follows a route function through the functions
it calls inside ``app`` (services, helpers, local imports) and reports whether
any of them is one of ``targets``.
"""

import ast
import inspect
import textwrap
from types import FunctionType, ModuleType

from test_route_permissions import routes

MAX_DEPTH = 8


def _callee(node: ast.Call, scope: dict):
    """Resolve ``name(...)`` and ``module.name(...)`` against the function's globals."""
    func = node.func
    if isinstance(func, ast.Name):
        return scope.get(func.id)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        owner = scope.get(func.value.id)
        if isinstance(owner, ModuleType):
            return getattr(owner, func.attr, None)
    return None


def _local_imports(tree: ast.AST) -> dict:
    """Names imported inside the function body (``from app.x import y``)."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
            module = __import__(node.module, fromlist=["_"])
            for alias in node.names:
                found[alias.asname or alias.name] = getattr(module, alias.name, None)
    return found


def reaches(function, targets, depth: int = 0, seen: set | None = None) -> bool:
    seen = set() if seen is None else seen
    function = inspect.unwrap(function)
    if function in targets:
        return True
    if (
        depth > MAX_DEPTH
        or function in seen
        or not isinstance(function, FunctionType)
        or not function.__module__.startswith("app")
    ):
        return False
    seen.add(function)
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    scope = {**function.__globals__, **_local_imports(tree)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = _callee(node, scope)
            if target is not None and reaches(target, targets, depth + 1, seen):
                return True
    return False


def write_routes():
    for method, path, route in routes():
        if method not in {"GET", "HEAD", "OPTIONS"}:
            yield method, path, route
