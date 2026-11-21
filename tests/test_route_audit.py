"""Every write route leaves an audit trail (CLAUDE.md, rule 11; audit finding A2).

A route passes when its function, or a function it calls inside ``app``
(followed through services and helpers), calls one of the audit writers below.
The few writes that are not worth auditing are listed in UNAUDITED with the
reason. A new POST/PUT/PATCH/DELETE route that records nothing fails here.

The check is static: it proves the route *can* reach an audit writer, not that
every branch does. ``tests/test_write_audit.py`` checks the critical routes
end to end.
"""

from route_analysis import reaches, write_routes

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


def reaches_audit(function) -> bool:
    return reaches(function, AUDIT_WRITERS)


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
