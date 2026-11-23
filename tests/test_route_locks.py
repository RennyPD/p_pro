"""Every write route takes the lock of its domain (CLAUDE.md, rule 8; audit finding M2).

A route passes when it reaches ``lock_scope`` (``lock_governance``,
``lock_finance``, ``lock_access``), the fine-grained ``lock_academic`` (Fase 3 G)
or the per-account row lock of the sign-in endpoints. Writes that change nothing shared are listed in UNLOCKED with the
reason. Static, like ``test_route_audit.py``.
"""

from route_analysis import reaches, write_routes

from app.services import account_sessions, write_locks

LOCKS = {
    write_locks.lock_scope,
    write_locks.lock_academic,
    account_sessions.lock_account,
}

# (method, path): why the route needs no lock.
UNLOCKED = {
    ("POST", "/auth/bootstrap"): "locks the users table itself (first administrator)",
    ("POST", "/auth/logout"): "revokes only the presented refresh token",
    ("POST", "/assessments/templates"): "personal template of the signed-in teacher",
    ("POST", "/community/notifications/read-all"): "own notifications read state",
    ("POST", "/community/notifications/{notification_id}/read"): "own notification read state",
    ("POST", "/community/announcements/preview"): "preview, writes nothing",
    ("POST", "/configuration/institution/preview"): "preview, writes nothing",
    ("POST", "/governance/equivalences/preview"): "preview, writes nothing",
    ("POST", "/finance/billing-plans/{plan_id}/preview"): "preview, writes nothing",
    ("POST", "/finance/students/{student_id}/simulate"): "simulation, writes nothing",
}


def test_every_write_route_takes_a_lock_or_is_documented():
    missing = sorted(
        f"{method} {path}"
        for method, path, route in write_routes()
        if (method, path) not in UNLOCKED and not reaches(route.endpoint, LOCKS)
    )
    assert missing == [], (
        "Write routes without a domain lock (lock_governance / lock_finance / lock_access, "
        "or justify in UNLOCKED):\n" + "\n".join(missing)
    )


def test_unlocked_list_has_no_stale_entries():
    current = {(method, path): route for method, path, route in write_routes()}
    stale = sorted(f"{m} {p}" for m, p in UNLOCKED if (m, p) not in current)
    assert stale == [], "Remove routes that no longer exist:\n" + "\n".join(stale)
    locked = sorted(
        f"{m} {p}"
        for m, p in UNLOCKED
        if (m, p) in current and reaches(current[m, p].endpoint, LOCKS)
    )
    assert locked == [], "These routes now take a lock; drop them from UNLOCKED:\n" + "\n".join(
        locked
    )
