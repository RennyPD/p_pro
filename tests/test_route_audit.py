"""Every write route leaves an audit trail (CLAUDE.md, rule 11; audit finding A2).

A route passes when its function, or a function it calls inside ``app``
(followed through services and helpers), calls one of the audit writers below.
The few writes that are not worth auditing are listed in UNAUDITED with the
reason. A new POST/PUT/PATCH/DELETE route that records nothing fails here.

The check is static: it proves the route *can* reach an audit writer, not that
every branch does. ``tests/test_write_audit.py`` checks the critical routes
end to end.
"""

import ast
import inspect
import textwrap
from types import FunctionType, ModuleType

from test_route_permissions import routes

from app.services import academic_grading, attendance_workflow, audit_log, finance_workflow

# Writers of an audit trail: the general log and the domain histories.
AUDIT_WRITERS = {
    audit_log.audit_event,  # audit_logs (record() calls it)
    academic_grading.record_change,  # grade_changes
    attendance_workflow.change,  # attendance_changes
    finance_workflow.event,  # finance_events
}

# (method, path): why the route records nothing.
UNAUDITED = {
    ("POST", "/community/notifications/read-all"): "own notifications read state",
    ("POST", "/community/notifications/{notification_id}/read"): "own notification read state",
    ("POST", "/academic/catalog/cart/{section_id}"): "student's own draft; confirm is audited",
    ("DELETE", "/academic/catalog/cart/{section_id}"): "student's own draft; confirm is audited",
    ("POST", "/assessments/templates"): "personal template; applying it is audited",
    ("POST", "/community/announcements/preview"): "preview, writes nothing",
    ("POST", "/configuration/institution/preview"): "preview, writes nothing",
    ("POST", "/governance/equivalences/preview"): "preview, writes nothing",
    ("POST", "/finance/billing-plans/{plan_id}/preview"): "preview, writes nothing",
    ("POST", "/finance/students/{student_id}/simulate"): "simulation, writes nothing",
}

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


def reaches_audit(function, depth: int = 0, seen: set | None = None) -> bool:
    seen = set() if seen is None else seen
    function = inspect.unwrap(function)
    if function in AUDIT_WRITERS:
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
            if target is not None and reaches_audit(target, depth + 1, seen):
                return True
    return False


def write_routes():
    for method, path, route in routes():
        if method not in {"GET", "HEAD", "OPTIONS"}:
            yield method, path, route


def test_every_write_route_records_an_audit_entry_or_is_documented():
    missing = sorted(
        f"{method} {path}"
        for method, path, route in write_routes()
        if (method, path) not in UNAUDITED and not reaches_audit(route.endpoint)
    )
    assert missing == [], (
        "Write routes without an audit entry (call record(...) or justify in UNAUDITED):\n"
        + "\n".join(missing)
    )


def test_unaudited_list_has_no_stale_entries():
    current = {(method, path): route for method, path, route in write_routes()}
    stale = sorted(f"{m} {p}" for m, p in UNAUDITED if (m, p) not in current)
    assert stale == [], "Remove routes that no longer exist:\n" + "\n".join(stale)
    audited = sorted(
        f"{m} {p}"
        for (m, p) in UNAUDITED
        if (m, p) in current and reaches_audit(current[m, p].endpoint)
    )
    assert audited == [], (
        "These routes now record an entry; drop them from UNAUDITED:\n" + "\n".join(audited)
    )


def test_detector_follows_services_and_rejects_silent_writes():
    def silent(db):
        db.commit()

    assert reaches_audit(audit_log.record)
    assert not reaches_audit(silent)
