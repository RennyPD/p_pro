"""Every API route is guarded by a role permission (CLAUDE.md, rule 3).

A route passes when its dependency tree includes require_permissions,
require_any_permission or require_personal. The only exceptions are listed in
SCOPE_CHECKED below: public sign-in endpoints and reads of the account's own data
or of records whose access is decided inside by the ensure_* scope helpers
(which themselves use permissions such as students.view or finance.view).
"""

from fastapi.routing import APIRoute

from app.permissions import PERMISSION_SLUGS
from main import app

# (method, path): why it does not need its own permission dependency.
SCOPE_CHECKED = {
    # Public or session endpoints.
    ("GET", "/health"): "health check",
    ("GET", "/health/ready"): "readiness check for the load balancer (no data)",
    ("POST", "/auth/bootstrap"): "first administrator, protected by bootstrap token",
    ("POST", "/auth/login"): "sign-in",
    ("POST", "/auth/refresh"): "session renewal",
    ("POST", "/auth/logout"): "sign-out",
    ("POST", "/auth/password-reset/request"): "public, same answer for every account",
    ("POST", "/auth/password-reset/confirm"): "public, authorized by the emailed link",
    ("GET", "/auth/sessions"): "own sessions",
    ("POST", "/auth/sessions/revoke-all"): "own sessions",
    ("POST", "/auth/change-password"): "own password",
    ("GET", "/auth/me"): "own account",
    ("GET", "/auth/email-preferences"): "own email preferences",
    ("PUT", "/auth/email-preferences"): "own email preferences",
    ("POST", "/auth/mfa/setup"): "own second factor",
    ("DELETE", "/auth/mfa/setup"): "own second factor",
    ("POST", "/auth/mfa/enable"): "own second factor",
    ("POST", "/auth/mfa/disable"): "own second factor",
    ("GET", "/access/me"): "own permissions",
    ("GET", "/dashboard/summary"): "own home, figures filtered by scope",
    ("GET", "/community/notifications"): "own notifications",
    ("POST", "/community/notifications/read-all"): "own notifications",
    ("POST", "/community/notifications/{notification_id}/read"): "own notifications",
    ("GET", "/module-views/mine"): "own read-only modules",
    ("GET", "/configuration/institution"): "institution name for the shell",
    ("GET", "/periods/"): "period names for filters",
    ("GET", "/school-years/"): "school year names for filters",
    ("GET", "/grading-scales/"): "scale definitions every grade screen needs to show values",
    ("GET", "/public/institution"): "public name and status of the addressed institution",
    ("GET", "/onboarding/checklist"): "settings.manage (require_permissions)",
    ("POST", "/platform/auth/login"): "platform sign-in with mandatory second factor",
    ("GET", "/platform/me"): "platform token (require_platform_admin)",
    ("GET", "/platform/institutions"): "platform token (require_platform_admin)",
    ("POST", "/platform/institutions"): "platform token (require_platform_admin)",
    (
        "POST",
        "/platform/institutions/{institution_id}/suspend",
    ): "platform token (require_platform_admin)",
    (
        "POST",
        "/platform/institutions/{institution_id}/reactivate",
    ): "platform token (require_platform_admin)",
    ("GET", "/platform/audit"): "platform token (require_platform_admin)",
    ("GET", "/public/signup"): "public sign-up page: plans and whether sign-up is open",
    ("GET", "/public/signup/code"): "public: whether a code is free (rate limited)",
    ("POST", "/public/signup"): "public self sign-up (rate limited; pending until verified)",
    ("GET", "/online-payments/options"): "payer scope: own account or linked children (finance)",
    ("POST", "/online-payments"): "payer scope checked in create_intent (linked children only)",
    ("GET", "/online-payments/{public_id}"): "the payer, or staff with finance.view",
    (
        "POST",
        "/online-payments/{public_id}/complete",
    ): "public bank return, trusted only by signature",
    (
        "GET",
        "/fiscal/documents/{document_id}.pdf",
    ): "account scope (accessible): payer or finance staff",
    ("GET", "/fiscal/payments/{payment_id}"): "account scope (accessible): payer or finance staff",
    ("GET", "/public/legal"): "public legal documents",
    ("GET", "/public/legal/{slug}"): "public legal documents",
    ("GET", "/legal/pending"): "any account; only administrators get documents to accept",
    ("POST", "/legal/accept"): "settings.manage checked in the route (institution administrators)",
    ("GET", "/public/demo"): "public: whether the demo is open",
    ("POST", "/public/demo/login"): "public demo entry (DEMO_ENABLED, demo institution only)",
    ("GET", "/billing/status"): "any account: only its own institution's plan status",
    ("POST", "/billing/webhooks/stripe"): "payment provider webhook, verified by its signature",
    ("GET", "/platform/plans"): "platform super administration (platform token)",
    ("POST", "/platform/plans"): "platform super administration (platform token)",
    ("PUT", "/platform/plans/{code}"): "platform super administration (platform token)",
    (
        "PUT",
        "/platform/institutions/{institution_id}/subscription",
    ): "platform super administration (platform token)",
    ("GET", "/students/{student_id}/report-card"): "own, linked guardian, staff or group teachers",
    ("GET", "/students/{student_id}/report-card.pdf"): "same scope as the report card",
    ("GET", "/class-groups/{class_group_id}/report-cards.pdf"): "ensure_group_access",
    ("GET", "/class-groups/{class_group_id}/period-report"): "ensure_group_access",
    ("GET", "/class-groups/{class_group_id}/period-report.csv"): "ensure_group_access",
    ("GET", "/class-groups/{class_group_id}/period-report.pdf"): "ensure_group_access",
    ("GET", "/school-years/{school_year_id}/promotion-summary"): "visible_groups only",
    (
        "PUT",
        "/class-groups/{class_group_id}/members/{member_id}/comments/{period_id}",
    ): "homeroom teacher, or grades.manage with academic scope (report_cards.can_comment)",
    ("GET", "/class-groups/"): "visible_groups: academic reach, own teacher groups, else none",
    ("GET", "/class-groups/{class_group_id}"): "ensure_group_access (same scope as the list)",
    ("GET", "/finance/options"): "transfer instructions shown to account holders",
    # Reads whose records are filtered by ensure_* / scope helpers.
    ("GET", "/academic/students/{student_id}/grades"): "ensure_student_access",
    ("GET", "/academic/students/{student_id}/schedule"): "ensure_student_access",
    ("GET", "/academic/teachers/{teacher_id}/schedule"): "ensure_teacher_access",
    ("GET", "/academic/sections/{section_id}/students"): "ensure_section_access",
    ("GET", "/academic/sections/academic-summary"): "sections in scope",
    ("GET", "/academic/students/{student_id}/profile"): "ensure_student_academic_access",
    ("GET", "/academic/sections/{section_id}/workspace"): "ensure_section_access",
    ("GET", "/academic/students/{student_id}/attendance-summary"): "ensure_student_access",
    ("GET", "/assessments/sections/{section_id}"): "ensure_section_access",
    ("GET", "/assessments/enrollments/{enrollment_id}/final"): "ensure_enrollment_access",
    ("GET", "/assessments/sections/{section_id}/finals"): "ensure_section_access",
    ("GET", "/attendances/sections/{section_id}/session"): "ensure_section_access",
    ("GET", "/attendances/"): "records in scope",
    ("GET", "/attendances/{attendance_id}"): "ensure_enrollment_access",
    ("GET", "/grades/"): "records in scope",
    ("GET", "/grades/{grade_id}"): "ensure_enrollment_access",
    ("GET", "/careers/"): "catalogue reference data",
    ("GET", "/careers/{career_id}"): "catalogue reference data",
    ("GET", "/subjects/"): "catalogue reference data",
    ("GET", "/subjects/{subject_id}"): "catalogue reference data",
    ("GET", "/curriculum/courses"): "catalogue reference data",
    ("GET", "/curriculum/students/{student_id}/progress"): "ensure_student_access",
    ("GET", "/sections/"): "sections in scope",
    ("GET", "/sections/{section_id}"): "ensure_section_access",
    ("GET", "/students/"): "students in scope",
    ("GET", "/students/{student_id}"): "ensure_student_academic_access",
    ("GET", "/teachers/"): "teachers in scope",
    ("GET", "/teachers/departments"): "reference data",
    ("GET", "/teachers/{teacher_id}"): "ensure_teacher_access",
    ("GET", "/teachers/{teacher_id}/workload"): "ensure_teacher_access",
    ("GET", "/enrollments/"): "records in scope",
    ("GET", "/enrollments/{enrollment_id}"): "ensure_enrollment_access",
    ("GET", "/governance/equivalences"): "rules that apply to the account's records",
    ("GET", "/governance/students/{student_id}/career-history"): "ensure_student_access",
    ("GET", "/governance/students/{student_id}/graduation-audit"): "ensure_student_access",
    ("GET", "/records/students/{student_id}/transcript"): "ensure_student_access",
    ("GET", "/documents/students/{student_id}/transcript.pdf"): "ensure_student_access",
    ("GET", "/documents/students/{student_id}/statement.pdf"): "ensure_student_access",
    ("GET", "/documents/sections/{section_id}/roster.pdf"): "ensure_section_access",
    ("GET", "/documents/students/{student_id}/enrollment-certificate.pdf"): "ensure_student_access",
    ("GET", "/documents/students/{student_id}/report-card.pdf"): "ensure_student_access",
    ("GET", "/community/students/{student_id}/guardians"): "ensure_student_access",
    ("GET", "/scheduling/classrooms"): "reference data for schedules",
    ("GET", "/scheduling/sections/{section_id}/meetings"): "ensure_section_access",
    ("GET", "/finance/students/{student_id}"): "ensure_student_access (finance scope)",
    ("GET", "/finance/students/{student_id}/payment-plans"): "ensure_student_access",
    ("GET", "/finance/students/{student_id}/statement"): "own account or finance scope",
    ("POST", "/finance/students/{student_id}/transfers"): "own account or finance scope",
    ("GET", "/finance/students/{student_id}/transfers"): "own account or finance scope",
    ("GET", "/finance/transfers/{identifier}/proof"): "own account or finance scope",
    ("GET", "/finance/payments/{identifier}/receipt.pdf"): "own account or finance scope",
    ("GET", "/operations/calendar"): "events for the account's audience and sections",
    ("GET", "/operations/alerts"): "students in scope",
    ("GET", "/operations/alerts/{alert_id}/interventions"): "ensure_student_academic_access",
    ("GET", "/operations/approvals/mine"): "own requests",
    ("POST", "/operations/approvals"): "request about a record in scope",
    ("GET", "/operations/students/{student_id}/documents"): "ensure_student_document_access",
    ("GET", "/operations/documents/{document_id}/download"): "ensure_student_document_access",
    ("GET", "/operations/task-sections"): "sections in scope",
    ("GET", "/operations/agenda"): "sections in scope",
    ("GET", "/operations/assignments"): "sections in scope",
    ("GET", "/operations/submissions/{submission_id}/revisions"): "own or managed submission",
    (
        "GET",
        "/operations/submissions/{submission_id}/revisions/{revision_id}/attachment",
    ): "own or managed submission",
}


def permission_slugs(dependant) -> set[str]:
    found = set(getattr(dependant.call, "nexo_permissions", ()) or ())
    for sub in dependant.dependencies:
        found |= permission_slugs(sub)
    return found


def flattened(items):
    """API routes, including those of included routers (expanded lazily by FastAPI)."""
    for route in items:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_candidates"):
            yield from flattened(route.effective_candidates())
        elif hasattr(route, "dependant") and hasattr(route, "methods"):
            yield route


def routes():
    for route in flattened(app.routes):
        for method in (route.methods or set()) - {"HEAD", "OPTIONS"}:
            yield method, route.path, route


def test_every_route_requires_a_permission_or_is_documented():
    unguarded = sorted(
        f"{method} {path}"
        for method, path, route in routes()
        if not permission_slugs(route.dependant) and (method, path) not in SCOPE_CHECKED
    )
    assert unguarded == [], "Routes without a permission dependency:\n" + "\n".join(unguarded)


def test_routes_only_use_catalog_permissions():
    used = set()
    for _, _, route in routes():
        used |= permission_slugs(route.dependant)
    assert used <= PERMISSION_SLUGS, used - PERMISSION_SLUGS


def test_exception_list_has_no_stale_entries():
    existing = {(method, path) for method, path, _ in routes()}
    assert set(SCOPE_CHECKED) <= existing, set(SCOPE_CHECKED) - existing
