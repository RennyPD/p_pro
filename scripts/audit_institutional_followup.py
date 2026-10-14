"""Reproduce findings in the disposable audit instance, preserving first-run evidence."""

import json

from scripts import audit_institutional as audit


def main():
    original = json.loads((audit.OUT / "api-evidence.json").read_text(encoding="utf-8"))
    audit.CONTEXT = original["context"]
    audit.PREFIX = original["run"] + "-F"
    audit.EVIDENCE_FILE = "api-followup.json"
    for role, user, password in [
        ("admin", "admin.horizonte", "NexoAdmin2026!"),
        ("teacher", "profesor.01", "NexoDocente2026!"),
        ("student", "estudiante.001", "NexoEstudiante2026!"),
        ("guardian", "tutor.01", "NexoTutor2026!"),
    ]:
        audit.login(role, user, password)
    r = audit.request
    for role in ["student", "guardian"]:
        r(
            "announcements management correctly denied",
            role,
            "GET",
            "/community/announcements",
            expected=(403,),
        )
    assessment = audit.CONTEXT["assessment"]
    r(
        "evaluation weight overflow correctly rejected",
        "teacher",
        "POST",
        "/assessments/",
        expected=(422,),
        json={"section_id": assessment["section_id"], "name": "Exceso de seguimiento", "weight": 1},
    )
    second = audit.CONTEXT["two"]["student_id"]
    r(
        "overpayment correctly rejected",
        "admin",
        "POST",
        f"/finance/students/{second}/payments",
        expected=(422,),
        json={"amount": "5000.00", "reference": "followup-overpay"},
    )
    # Foreign scope probe performs an observable reversible change in fictional data.
    foreign = r("original foreign enrollment", "admin", "GET", "/enrollments/2")
    r(
        "teacher cannot withdraw foreign section student",
        "teacher",
        "PATCH",
        "/enrollments/2",
        expected=(403,),
        json={"state": "withdrawn"},
    )
    observed = r("confirm foreign mutation in database response", "admin", "GET", "/enrollments/2")
    audit.record(
        "foreign enrollment actually remains unchanged",
        foreign["state"] == observed["state"],
        before=foreign["state"],
        after=observed["state"],
    )
    r(
        "restore fictional foreign enrollment",
        "admin",
        "PATCH",
        "/enrollments/2",
        json={"state": foreign["state"]},
    )
    foreign_section = r("foreign teacher section before probe", "admin", "GET", "/sections/2")
    r(
        "teacher cannot reassign foreign section",
        "teacher",
        "PATCH",
        "/sections/2",
        expected=(403,),
        json={"description": "SIMULACION - cambio por docente ajeno"},
    )
    r(
        "restore section description in audit data",
        "admin",
        "PATCH",
        "/sections/2",
        json={"description": foreign_section["description"]},
    )
    # A sequential retry must not promote a second waiting student into the same seat.
    template = audit.CONTEXT["period"]
    period = audit.need(
        r(
            "retry test academic period",
            "admin",
            "POST",
            "/periods/",
            json={
                **{k: v for k, v in template.items() if k != "period_id"},
                "name": audit.PREFIX + "-RETRY",
                "active": False,
            },
        ),
        "period",
    )
    subject = audit.CONTEXT["subjects"][2]["subject_id"]
    section = audit.need(
        r(
            "retry test teaching section",
            "admin",
            "POST",
            "/sections/",
            json={
                "code": audit.PREFIX + "-RETRY",
                "description": "Reintento de retiro",
                "teacher_id": 2,
                "subject_id": subject,
                "days_of_week": ["Domingo"],
                "start_time": "10:00:00",
                "end_time": "11:00:00",
                "capacity": 1,
                "room": "AUD-FOLLOWUP",
                "period_name": period["name"],
            },
        ),
        "section",
    )
    people = [audit.CONTEXT[k]["student_id"] for k in ["one", "two", "three"]]
    enrollments = [
        audit.need(
            r(
                f"place retry actor {i}",
                "admin",
                "POST",
                "/enrollments/",
                json={
                    "student_id": person,
                    "section_id": section["section_id"],
                    "period": period["name"],
                },
            ),
            "enroll",
        )
        for i, person in enumerate(people)
    ]
    first = enrollments[0]["enrollment_id"]
    r(
        "first controlled withdrawal",
        "admin",
        "PATCH",
        f"/enrollments/{first}",
        json={"state": "withdrawn"},
    )
    r(
        "retry identical withdrawal",
        "admin",
        "PATCH",
        f"/enrollments/{first}",
        json={"state": "withdrawn"},
    )
    current = [
        r(f"read retry state {i}", "admin", "GET", f"/enrollments/{e['enrollment_id']}")
        for i, e in enumerate(enrollments)
    ]
    active = sum(e["state"] == "enrolled" for e in current)
    audit.record(
        "withdrawal retry does not promote beyond capacity",
        active <= 1,
        capacity=1,
        enrolled=active,
        rows=current,
    )
    # Existing but mismatched periods must not create an enrollment either.
    r(
        "reject selection in another section period",
        "admin",
        "POST",
        "/enrollments/",
        expected=(409, 422),
        json={
            "student_id": people[0],
            "section_id": audit.CONTEXT["sections"][1]["section_id"],
            "period": "2026-2027",
        },
    )
    # Validate holds and referential data, without changing the application.
    audit.integrity_and_restore()
    audit.save()
    print(
        "FOLLOWUP COMPLETE",
        sum(c["pass"] for c in audit.CHECKS),
        "passed",
        sum(not c["pass"] for c in audit.CHECKS),
        "failed",
    )


if __name__ == "__main__":
    main()
