"""Complete graduation, equivalence, documents and data-quality acceptance evidence."""

import json
import sqlite3

from scripts import audit_institutional as audit


def main():
    original = json.loads((audit.OUT / "api-evidence.json").read_text(encoding="utf-8"))
    audit.CONTEXT = original["context"]
    audit.PREFIX = original["run"] + "-G"
    audit.EVIDENCE_FILE = "api-completion.json"
    audit.login("admin", "admin.horizonte", "NexoAdmin2026!")
    audit.login("teacher", "profesor.01", "NexoDocente2026!")
    audit.login("two", original["run"] + "-two", "AuditOnly2026!")
    r = audit.request
    student = audit.CONTEXT["two"]["student_id"]
    period = audit.CONTEXT["period"]
    r(
        "activate simulated teaching cycle",
        "admin",
        "PATCH",
        f"/periods/{period['period_id']}",
        json={"active": True},
    )
    section = audit.CONTEXT["sections"][1]["section_id"]
    enrollment = audit.need(
        r(
            "prerequisite now unlocks continuation",
            "two",
            "POST",
            f"/academic/catalog/sections/{section}/select",
        ),
        "selection",
    )
    assessment = audit.need(
        r(
            "create continuation final evaluation",
            "teacher",
            "POST",
            "/assessments/",
            json={"section_id": section, "name": "Continuidad final", "weight": 100},
        ),
        "assessment",
    )
    grade = audit.need(
        r(
            "published zero is valid",
            "teacher",
            "POST",
            "/grades/",
            json={
                "enrollment_id": enrollment["enrollment_id"],
                "assessment_id": assessment["assessment_id"],
                "grade_type": assessment["name"],
                "grade_value": 0,
                "date_recorded": str(audit.TODAY),
                "status": "published",
            },
        ),
        "grade",
    )
    r(
        "correct zero with audit reason",
        "teacher",
        "PATCH",
        f"/grades/{grade['grade_id']}",
        json={"grade_value": 90, "reason": "Corrección ficticia documentada"},
    )
    history = r(
        "grade correction immutable history",
        "teacher",
        "GET",
        f"/grades/{grade['grade_id']}/history",
    )
    audit.record(
        "zero correction keeps previous value and actor",
        any(
            h.get("previous_value") == 0 and h.get("new_value") == 90 and h.get("changed_by")
            for h in history
        ),
        history=history,
    )
    r(
        "close continuation final evaluation",
        "teacher",
        "POST",
        f"/assessments/{assessment['assessment_id']}/close",
        json={"reason": "Resultados definitivos revisados"},
    )
    graduated = r(
        "student now meets graduation requirements",
        "two",
        "GET",
        f"/governance/students/{student}/graduation-audit",
    )
    audit.record(
        "graduation becomes eligible only after required courses",
        graduated and graduated.get("eligible") is True,
        graduation=graduated,
    )
    subjects = audit.CONTEXT["subjects"]
    rule = {
        "career_id": audit.CONTEXT["career_id"],
        "source_subject_id": subjects[0]["subject_id"],
        "target_subject_id": subjects[2]["subject_id"],
        "curriculum_version": "AUD-1",
        "reason": "Regla ficticia de aceptación",
        "notes": "No crea notas nuevas",
    }
    r(
        "equivalence previews academic impact",
        "admin",
        "POST",
        "/governance/equivalences/preview",
        json=rule,
    )
    before = r("grades before recognition", "two", "GET", f"/academic/students/{student}/grades")
    created = audit.need(
        r(
            "create valid versioned equivalence",
            "admin",
            "POST",
            "/governance/equivalences",
            json=rule,
        ),
        "equivalence",
    )
    progress = r(
        "recognition updates credits", "two", "GET", f"/curriculum/students/{student}/progress"
    )
    recognized = [c for c in progress["courses"] if c["subject_id"] == subjects[2]["subject_id"]]
    audit.record(
        "equivalent credits recognized transparently",
        bool(recognized) and recognized[0].get("recognition_type") == "equivalence",
        courses=recognized,
    )
    after = r("grades after recognition", "two", "GET", f"/academic/students/{student}/grades")
    audit.record("equivalence does not fabricate numeric grades", before == after)
    identifier = created["course_equivalence_id"]
    r(
        "equivalence impact before deactivation",
        "admin",
        "GET",
        f"/governance/equivalences/{identifier}/impact",
        params={"active": False},
    )
    r(
        "deactivate equivalence with reason",
        "admin",
        "PATCH",
        f"/governance/equivalences/{identifier}",
        json={
            "notes": "Regla de prueba desactivada",
            "active": False,
            "reason": "Fin de simulación",
        },
    )
    r("equivalence traceability", "admin", "GET", f"/governance/equivalences/{identifier}/history")
    transcript = r(
        "definitive academic transcript", "two", "GET", f"/records/students/{student}/transcript"
    )
    audit.CONTEXT["graduated_transcript"] = transcript
    for path in [
        f"/documents/students/{student}/transcript.pdf",
        f"/documents/students/{student}/enrollment-certificate.pdf",
        f"/documents/students/{student}/report-card.pdf",
    ]:
        r("download internal document " + path, "two", "GET", path)
    # The live seed's capacity problems must not be confused with fresh API race tests.
    with sqlite3.connect(f"file:{audit.DB.as_posix()}?mode=ro", uri=True) as db:
        tables = [v[0] for v in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        audit.CONTEXT["audit_tables"] = tables
        section_table = next(t for t in tables if t in {"sections", "section"})
        enrollment_table = next(t for t in tables if t in {"enrollments", "enrollment"})
        rows = db.execute(
            f'SELECT s.section_id,s.code,s.capacity,COUNT(e.enrollment_id) FROM "{section_table}" s JOIN "{enrollment_table}" e ON e.section_id=s.section_id WHERE s.section_id<=15 AND e.state=\'enrolled\' GROUP BY s.section_id HAVING COUNT(e.enrollment_id)>s.capacity'
        ).fetchall()
        audit.record(
            "institutional demo seed respects section capacities",
            not rows,
            overfull_demo_sections=rows,
        )
    audit.integrity_and_restore()
    audit.save()
    print(
        "COMPLETION",
        sum(c["pass"] for c in audit.CHECKS),
        "passed",
        sum(not c["pass"] for c in audit.CHECKS),
        "failed",
    )


if __name__ == "__main__":
    main()
