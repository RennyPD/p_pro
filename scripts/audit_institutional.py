"""Acceptance evidence against the isolated audit server; never targets the live app.

Run only after migrating and seeding backups/institutional-audit-20261014/audit.db.
This is an audit harness, not an application repair or a production seed command.
"""

from __future__ import annotations

import base64
import json
import sqlite3
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Barrier

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backups" / "institutional-audit-20261014"
DB = OUT / "audit.db"
URL = "http://127.0.0.2:8001"
TODAY = date.today()
PREFIX = "AUD-" + datetime.now().strftime("%H%M%S")
CHECKS: list[dict] = []
CLIENTS: dict[str, httpx.Client] = {}
CONTEXT: dict = {}
EVIDENCE_FILE = "api-evidence.json"


def record(name, ok, **evidence):
    item = {"name": name, "pass": bool(ok), **evidence}
    CHECKS.append(item)
    print(json.dumps(item, ensure_ascii=True), flush=True)
    save()


def save():
    OUT.mkdir(exist_ok=True)
    (OUT / EVIDENCE_FILE).write_text(
        json.dumps(
            {
                "run": PREFIX,
                "url": URL,
                "database": str(DB),
                "checks": CHECKS,
                "context": CONTEXT,
                "passed": sum(c["pass"] for c in CHECKS),
                "failed": sum(not c["pass"] for c in CHECKS),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def request(name, role, method, path, expected=(200,), **kwargs):
    started = time.perf_counter()
    response = CLIENTS[role].request(method, path, **kwargs)
    try:
        body = response.json()
    except ValueError:
        body = {
            "bytes": len(response.content),
            "content_type": response.headers.get("content-type"),
        }
    ok = response.status_code in expected
    evidence = {
        "role": role,
        "method": method,
        "path": path,
        "status": response.status_code,
        "expected": list(expected),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    if not ok:
        evidence["response"] = str(body)[:1800]
    record(name, ok, **evidence)
    return body if ok else None


def need(value, label):
    if value is None:
        raise RuntimeError("Scenario cannot continue after failed prerequisite: " + label)
    return value


def scenario(name, function):
    try:
        function()
    except Exception as exc:
        record(
            name + ": incomplete scenario",
            False,
            classification="harness-or-prerequisite",
            error=str(exc),
            trace=traceback.format_exc()[-1800:],
        )


def login(role, username, password):
    client = httpx.Client(base_url=URL, timeout=40, trust_env=False, follow_redirects=True)
    response = client.post("/auth/login", json={"username": username, "password": password})
    record("login " + role, response.status_code == 200, role=role, status=response.status_code)
    payload = response.json()
    client.headers["Authorization"] = "Bearer " + payload["access_token"]
    CLIENTS[role] = client
    return payload["user"]


def smoke_and_scope():
    specs = [
        ("admin", "admin.horizonte", "NexoAdmin2026!"),
        ("teacher", "profesor.01", "NexoDocente2026!"),
        ("student", "estudiante.001", "NexoEstudiante2026!"),
        ("guardian", "tutor.01", "NexoTutor2026!"),
    ]
    CONTEXT["actors"] = {r: login(r, u, p) for r, u, p in specs}
    for role in CLIENTS.copy():
        for path in [
            "/auth/me",
            "/access/me",
            "/dashboard/summary",
            "/configuration/institution",
            "/community/notifications",
            "/community/announcements",
            "/operations/agenda",
            "/operations/assignments",
        ]:
            request(
                "baseline " + path,
                role,
                "GET",
                path,
                expected=(403,)
                if path == "/community/announcements" and role in {"student", "guardian"}
                else (200,),
            )
    for path in [
        "/students/",
        "/teachers/",
        "/careers/",
        "/subjects/",
        "/sections/",
        "/periods/",
        "/curriculum/courses/",
        "/operations/analytics/summary",
        "/operations/analytics/academic",
        "/operations/alerts",
        "/operations/admissions",
        "/finance/accounts",
        "/users/",
        "/roles/",
        "/access/permissions",
        "/audit/",
        "/scheduling/classrooms",
    ]:
        request("admin catalogue " + path, "admin", "GET", path)
    for role in ["student", "guardian", "teacher"]:
        for path in ["/users/", "/operations/analytics/summary", "/finance/accounts"]:
            request("deny institutional data " + path, role, "GET", path, expected=(403,))
    for path in [
        "/academic/students/1/grades",
        "/academic/students/1/schedule",
        "/academic/students/1/profile",
        "/academic/students/1/attendance-summary",
        "/curriculum/students/1/progress",
        "/governance/students/1/graduation-audit",
        "/records/students/1/transcript",
        "/finance/students/1",
        "/academic/catalog",
        "/academic/catalog/summary",
        "/academic/catalog/cart",
    ]:
        request("student own " + path, "student", "GET", path)
    for path in [
        "/academic/students/2/grades",
        "/academic/students/2/schedule",
        "/finance/students/2",
        "/records/students/2/transcript",
        "/academic/teachers/1/schedule",
    ]:
        request("deny another person " + path, "student", "GET", path, expected=(403,))
    request("teacher own schedule", "teacher", "GET", "/academic/teachers/1/schedule")
    request(
        "teacher foreign schedule",
        "teacher",
        "GET",
        "/academic/teachers/2/schedule",
        expected=(403,),
    )
    request("teacher own workspace", "teacher", "GET", "/academic/sections/1/workspace")
    request(
        "teacher foreign workspace",
        "teacher",
        "GET",
        "/academic/sections/2/workspace",
        expected=(403,),
    )
    own = request("teacher scoped grade list", "teacher", "GET", "/grades/") or []
    history = (
        request("teacher shared student history", "teacher", "GET", "/academic/students/1/grades")
        or []
    )
    extra = [g for g in history if g.get("grade_id") not in {v["grade_id"] for v in own}]
    record(
        "teacher student-history respects own section-grade scope",
        not extra,
        extra_grade_ids=[v.get("grade_id") for v in extra],
        sample=extra[:2],
    )
    family = need(
        request("guardian linked overview", "guardian", "GET", "/operations/guardian/overview"),
        "family",
    )
    CONTEXT["guardian_linked_student_ids"] = [v["student_id"] for v in family]
    record(
        "guardian overview excludes unrelated students",
        all(v["student_id"] != 120 for v in family),
        count=len(family),
    )
    for path in ["/academic/students/120/grades", "/finance/students/120", "/students/120"]:
        request("deny guardian foreign data " + path, "guardian", "GET", path, expected=(403,))
    # Probe whether the general selection manager bypasses teacher ownership.
    enrollment = request("get known foreign enrollment", "admin", "GET", "/enrollments/2")
    if enrollment:
        request(
            "teacher cannot change foreign enrollment",
            "teacher",
            "PATCH",
            "/enrollments/2",
            expected=(403,),
            json={"state": enrollment["state"]},
        )
    private = httpx.Client(base_url=URL, trust_env=False)
    record("anonymous students denied", private.get("/students/").status_code == 401)
    private.close()


def institutional_cycle():
    periods = need(request("save initial period", "admin", "GET", "/periods/"), "periods")
    CONTEXT["original_active_period"] = next((p for p in periods if p["active"]), None)
    career = need(
        request(
            "create professional test program",
            "admin",
            "POST",
            "/careers/",
            json={
                "code": PREFIX,
                "name": "Simulación institucional integral " + PREFIX,
                "description": "Programa ficticio de aceptación",
                "degree_title": "Título de prueba",
                "required_credits": 3,
                "duration_terms": 2,
                "curriculum_version": "AUD-1",
            },
        ),
        "career",
    )
    CONTEXT["career_id"] = career["career_id"]
    subjects = []
    for i in range(3):
        sub = need(
            request(
                f"create catalogue subject {i}",
                "admin",
                "POST",
                "/subjects/",
                json={
                    "code": f"{PREFIX}-{i}",
                    "description": [
                        "Fundamentos de prueba",
                        "Continuidad de prueba",
                        "Electiva de prueba",
                    ][i],
                },
            ),
            "subject",
        )
        subjects.append(sub)
        request(
            f"link curriculum subject {i}",
            "admin",
            "POST",
            "/curriculum/courses",
            json={
                "career_id": career["career_id"],
                "subject_id": sub["subject_id"],
                "term_number": 1 if i != 1 else 2,
                "credits": 3,
                "curriculum_version": "AUD-1",
                "course_type": "elective" if i == 2 else "required",
                "prerequisite_subject_id": subjects[0]["subject_id"] if i == 1 else None,
            },
        )
    CONTEXT["subjects"] = subjects
    period = need(
        request(
            "open semester for simulated cycle",
            "admin",
            "POST",
            "/periods/",
            json={
                "name": PREFIX,
                "start_date": str(TODAY - timedelta(days=14)),
                "end_date": str(TODAY + timedelta(days=70)),
                "active": True,
                "status": "active",
                "registration_start": str(TODAY - timedelta(days=20)),
                "registration_end": str(TODAY + timedelta(days=10)),
                "withdrawal_deadline": str(TODAY + timedelta(days=30)),
                "period_type": "semester",
                "sequence": 2,
                "academic_year": str(TODAY.year),
            },
        ),
        "period",
    )
    CONTEXT["period"] = period
    sections = []
    for i, s in enumerate(subjects):
        sections.append(
            need(
                request(
                    f"create teaching section {i}",
                    "admin",
                    "POST",
                    "/sections/",
                    json={
                        "code": f"{PREFIX}-S{i}",
                        "description": "Sección ficticia",
                        "subject_id": s["subject_id"],
                        "teacher_id": 1,
                        "days_of_week": ["Miércoles"],
                        "start_time": f"{18 + i:02}:00:00",
                        "end_time": f"{19 + i:02}:00:00",
                        "capacity": 1,
                        "room": f"AUD-{i}",
                        "period_name": period["name"],
                    },
                ),
                "section",
            )
        )
    CONTEXT["sections"] = sections
    for suffix in ["one", "two", "three"]:
        admission = need(
            request(
                "receive admission " + suffix,
                "admin",
                "POST",
                "/operations/admissions",
                json={
                    "first_name": "Aspirante",
                    "last_name": suffix,
                    "email": f"{PREFIX}-{suffix}@example.com",
                    "telephone": "8095550000",
                    "career_id": career["career_id"],
                },
            ),
            "admission",
        )
        aid = admission["admission_application_id"]
        request(
            "block unreviewed enrollment " + suffix,
            "admin",
            "POST",
            f"/operations/admissions/{aid}/enroll",
            expected=(409,),
        )
        for before, after in [("submitted", "review"), ("review", "accepted")]:
            request(
                "admission " + suffix + " " + after,
                "admin",
                "PATCH",
                f"/operations/admissions/{aid}",
                json={
                    "status": after,
                    "expected_status": before,
                    "reason": "Evidencia ficticia revisada",
                },
            )
        student = need(
            request(
                "create student from admission " + suffix,
                "admin",
                "POST",
                f"/operations/admissions/{aid}/enroll",
            ),
            "student",
        )
        retry = request(
            "retry admission enrollment " + suffix,
            "admin",
            "POST",
            f"/operations/admissions/{aid}/enroll",
        )
        record("admission retry is idempotent " + suffix, retry == student)
        role_id = CONTEXT["actors"]["student"]["role_id"]
        username = f"{PREFIX}-{suffix}"
        request(
            "provision student portal " + suffix,
            "admin",
            "POST",
            "/users/",
            json={
                "username": username,
                "email": f"portal-{username}@example.com",
                "password": "AuditOnly2026!",
                "role_id": role_id,
                "student_id": student["student_id"],
            },
        )
        login(suffix, username, "AuditOnly2026!")
        CONTEXT[suffix] = student
    sid = sections[0]["section_id"]
    request(
        "block prerequisite before pass",
        "one",
        "POST",
        f"/academic/catalog/sections/{sections[1]['section_id']}/select",
        expected=(409,),
    )
    selected = need(
        request(
            "student chooses own subject", "one", "POST", f"/academic/catalog/sections/{sid}/select"
        ),
        "selection",
    )
    request(
        "duplicate selection blocked",
        "one",
        "POST",
        f"/academic/catalog/sections/{sid}/select",
        expected=(409,),
    )
    waiting = need(
        request(
            "full section enters waitlist",
            "two",
            "POST",
            f"/academic/catalog/sections/{sid}/select",
        ),
        "waitlist",
    )
    record(
        "capacity respected sequentially",
        selected["state"] == "enrolled" and waiting["state"] == "waitlisted",
    )
    request(
        "withdraw within authorized deadline",
        "one",
        "POST",
        f"/academic/catalog/sections/{sid}/withdraw",
    )
    promoted = request("read promoted student", "two", "GET", "/enrollments/") or []
    record(
        "waitlist promotion after withdrawal",
        any(e["section_id"] == sid and e["state"] == "enrolled" for e in promoted),
    )
    # Continue teaching with the promoted student.
    enrollment = next(e for e in promoted if e["section_id"] == sid)
    CONTEXT["teaching_enrollment"] = enrollment
    subject2 = sections[2]["section_id"]
    request(
        "set academic hold",
        "admin",
        "PATCH",
        f"/students/{CONTEXT['one']['student_id']}",
        json={"academic_hold": True},
    )
    request(
        "hold blocks selection",
        "one",
        "POST",
        f"/academic/catalog/sections/{subject2}/select",
        expected=(409,),
    )
    request(
        "remove test hold",
        "admin",
        "PATCH",
        f"/students/{CONTEXT['one']['student_id']}",
        json={"academic_hold": False},
    )
    assessment = need(
        request(
            "teacher creates full evaluation plan",
            "teacher",
            "POST",
            "/assessments/",
            json={
                "section_id": sid,
                "name": "Proyecto integral",
                "weight": 100,
                "due_date": str(TODAY + timedelta(days=5)),
            },
        ),
        "assessment",
    )
    CONTEXT["assessment"] = assessment
    request(
        "reject plan above 100 percent",
        "teacher",
        "POST",
        "/assessments/",
        expected=(422,),
        json={"section_id": sid, "name": "Exceso", "weight": 1},
    )
    task = need(
        request(
            "teacher creates linked assignment",
            "teacher",
            "POST",
            "/operations/assignments",
            json={
                "section_id": sid,
                "title": "Proyecto institucional de prueba",
                "instructions": "Entrega ficticia para aceptación integral",
                "due_at": str(datetime.now() + timedelta(days=2)),
                "max_score": 50,
                "assessment_id": assessment["assessment_id"],
            },
        ),
        "task",
    )
    CONTEXT["task"] = task
    request(
        "withdrawn student cannot submit",
        "one",
        "POST",
        f"/operations/assignments/{task['assignment_id']}/submit",
        expected=(403, 404),
        json={"content": "No debería admitirse"},
    )
    submission = need(
        request(
            "active student submits task",
            "two",
            "POST",
            f"/operations/assignments/{task['assignment_id']}/submit",
            json={"content": "Respuesta ficticia completa"},
        ),
        "submission",
    )
    request(
        "teacher scores task",
        "teacher",
        "PATCH",
        f"/operations/submissions/{submission['submission_id']}/grade",
        json={"score": 40, "feedback": "Evidencia suficiente"},
    )
    request(
        "transfer task to draft grades",
        "teacher",
        "POST",
        f"/operations/assignments/{task['assignment_id']}/transfer-grades",
        json={"reason": "Verificado durante auditoría"},
    )
    request(
        "retry task grade transfer",
        "teacher",
        "POST",
        f"/operations/assignments/{task['assignment_id']}/transfer-grades",
        json={"reason": "Reintento controlado"},
    )
    private = (
        request(
            "student cannot see drafts",
            "two",
            "GET",
            f"/academic/students/{CONTEXT['two']['student_id']}/grades",
        )
        or []
    )
    record("draft result stays private", len(private) == 0)
    draft = need(
        request(
            "teacher sees normalized draft", "teacher", "GET", f"/academic/sections/{sid}/workspace"
        ),
        "workspace",
    )
    row = next(r for r in draft["roster"] if r["enrollment_id"] == enrollment["enrollment_id"])
    record(
        "task score normalized 40 of 50 to 80",
        any(g["grade_value"] == 80 and g["status"] == "draft" for g in row["grades"]),
    )
    request(
        "block close before all notes published",
        "teacher",
        "POST",
        f"/assessments/{assessment['assessment_id']}/close",
        expected=(409,),
        json={"reason": "Intento de cierre prematuro"},
    )
    request(
        "publish teacher results",
        "teacher",
        "POST",
        f"/grades/assessments/{assessment['assessment_id']}/publish",
    )
    request(
        "close complete evaluation",
        "teacher",
        "POST",
        f"/assessments/{assessment['assessment_id']}/close",
        json={"reason": "Notas verificadas"},
    )
    final = request(
        "read definitive result",
        "two",
        "GET",
        f"/assessments/enrollments/{enrollment['enrollment_id']}/final",
    )
    record(
        "definitive result equals 80 and passed",
        final
        and final.get("final")
        and final.get("weighted_grade") == 80
        and final.get("status") == "passed",
        result=final,
    )
    request(
        "closed evaluation rejects correction",
        "teacher",
        "POST",
        "/grades/",
        expected=(409,),
        json={
            "enrollment_id": enrollment["enrollment_id"],
            "assessment_id": assessment["assessment_id"],
            "grade_type": assessment["name"],
            "grade_value": 90,
            "date_recorded": str(TODAY),
        },
    )
    request(
        "record explicit attendance",
        "teacher",
        "POST",
        "/attendances/bulk",
        json={
            "section_id": sid,
            "date": str(TODAY),
            "reason": "Sesión de simulación",
            "records": [{"enrollment_id": enrollment["enrollment_id"], "status": "present"}],
        },
    )
    request(
        "reject unjustified excused state",
        "teacher",
        "POST",
        "/attendances/bulk",
        expected=(422,),
        json={
            "section_id": sid,
            "date": str(TODAY),
            "reason": "Control de justificación",
            "records": [{"enrollment_id": enrollment["enrollment_id"], "status": "excused"}],
        },
    )
    preview = request(
        "inspect semester close", "admin", "GET", f"/periods/{period['period_id']}/closing-preview"
    )
    CONTEXT["closing_preview"] = preview
    request(
        "close simulated semester",
        "admin",
        "POST",
        f"/periods/{period['period_id']}/close",
        json={"reason": "Cierre integral de aceptación"},
    )
    progress = request(
        "student earned curriculum credits",
        "two",
        "GET",
        f"/curriculum/students/{CONTEXT['two']['student_id']}/progress",
    )
    record(
        "published pass contributes three earned credits",
        progress and progress.get("completed_credits") == 3,
        progress=progress,
    )
    request(
        "closed semester rejects attendance",
        "teacher",
        "POST",
        "/attendances/bulk",
        expected=(409,),
        json={
            "section_id": sid,
            "date": str(TODAY),
            "records": [{"enrollment_id": enrollment["enrollment_id"], "status": "absent"}],
            "reason": "No debe cambiar cerrado",
        },
    )
    CONTEXT["graduation_result"] = request(
        "inspect graduation eligibility",
        "two",
        "GET",
        f"/governance/students/{CONTEXT['two']['student_id']}/graduation-audit",
    )
    request(
        "reopen semester with traceability",
        "admin",
        "POST",
        f"/periods/{period['period_id']}/reopen",
        json={"reason": "Continuación controlada de auditoría"},
    )
    request(
        "period closure audit available", "admin", "GET", f"/periods/{period['period_id']}/history"
    )


def finance_and_communications():
    student_id = CONTEXT["two"]["student_id"]
    root = f"/finance/students/{student_id}"
    request(
        "cash charge with cents",
        "admin",
        "POST",
        root + "/charges",
        json={"description": "Cargo ficticio", "amount": "1000.01", "due_date": str(TODAY)},
    )
    payload = {
        "amount": "200.01",
        "reference": PREFIX + "-cash",
        "idempotency_key": PREFIX + "-cash-key",
    }
    first = request(
        "record fictitious cash receipt", "admin", "POST", root + "/payments", json=payload
    )
    retry = request(
        "retry identical cash posting", "admin", "POST", root + "/payments", json=payload
    )
    record("cash retry cannot debit twice", first == retry)
    request(
        "reject excessive decimal money",
        "admin",
        "POST",
        root + "/payments",
        expected=(422,),
        json={"amount": "0.001", "reference": "invalid-cents"},
    )
    request(
        "reject overpayment",
        "admin",
        "POST",
        root + "/payments",
        expected=(422,),
        json={"amount": "5000.00", "reference": "overpay"},
    )
    proof = base64.b64encode(b"%PDF-1.4\n% Fictional audit proof\n%%EOF").decode()
    transfer = need(
        request(
            "student reports fictitious transfer",
            "two",
            "POST",
            root + "/transfers",
            json={
                "amount": "100.00",
                "reference": PREFIX + "-transfer",
                "bank": "Banco ficticio",
                "proof_base64": proof,
            },
        ),
        "transfer",
    )
    CONTEXT["transfer"] = transfer
    tid = transfer.get(
        "transfer_id", transfer.get("payment_transfer_id", transfer.get("transfer_request_id"))
    )
    if tid is None:
        raise RuntimeError("Inspect transfer shape: " + str(transfer)[:900])
    request(
        "private proof denied to another student",
        "one",
        "GET",
        f"/finance/transfers/{tid}/proof",
        expected=(403,),
    )
    request(
        "student cannot approve transfer",
        "two",
        "POST",
        f"/finance/transfers/{tid}/review",
        expected=(403,),
        json={"approve": True, "reason": "No autorizado"},
    )
    request(
        "finance manually approves simulated transfer",
        "admin",
        "POST",
        f"/finance/transfers/{tid}/review",
        json={"approve": True, "reason": "Ingreso ficticio verificado"},
    )
    before = request("balance after approved transfer", "two", "GET", root)
    record(
        "cent-level balance is 700 DOP",
        before and before.get("balance") == 700,
        balance=before.get("balance") if before else None,
    )
    request(
        "simulator executes without payment posting",
        "admin",
        "POST",
        root + "/simulate",
        json={"amount": "10.00", "outcome": "approved"},
    )
    after = request("balance after simulation unchanged", "two", "GET", root)
    record("simulator never moves money", before == after)
    request(
        "create monthly payment commitments",
        "admin",
        "POST",
        root + "/payment-plans",
        json={
            "name": "Plan ficticio",
            "installments": 3,
            "first_due_date": str(TODAY + timedelta(days=1)),
        },
    )
    message = {
        "title": "Aviso de simulación",
        "body": "Mensaje ficticio solo para el entorno de auditoría",
        "audience": "section",
        "section_id": CONTEXT["sections"][0]["section_id"],
    }
    preview = need(
        request(
            "teacher previews bounded audience",
            "teacher",
            "POST",
            "/community/announcements/preview",
            json=message,
        ),
        "audience",
    )
    published = request(
        "teacher sends internally to own section",
        "teacher",
        "POST",
        "/community/announcements",
        json={
            **message,
            "expected_recipients": preview["fingerprint"],
            "delivery_key": PREFIX + "-message",
        },
    )
    request(
        "retry announcement without duplicates",
        "teacher",
        "POST",
        "/community/announcements",
        json={
            **message,
            "expected_recipients": preview["fingerprint"],
            "delivery_key": PREFIX + "-message",
        },
    )
    notices = (
        request("selected student receives announcement", "two", "GET", "/community/notifications")
        or []
    )
    record(
        "section announcement delivered once",
        published
        and sum(n.get("announcement_id") == published["announcement_id"] for n in notices) == 1,
    )
    request(
        "teacher global broadcast denied",
        "teacher",
        "POST",
        "/community/announcements/preview",
        expected=(403,),
        json={**message, "audience": "all", "section_id": None},
    )


def edge_cases():
    sid = CONTEXT["one"]["student_id"]
    second = CONTEXT["two"]["student_id"]
    period = CONTEXT["period"]
    subject = CONTEXT["subjects"][2]
    # Read-only empirical probe: no simultaneous selection may exceed the only seat.
    statuses = []
    for attempt in range(8):
        race_period = need(
            request(
                f"race academic period {attempt}",
                "admin",
                "POST",
                "/periods/",
                json={
                    **{k: v for k, v in period.items() if k != "period_id"},
                    "name": PREFIX + f"-R{attempt}",
                    "active": False,
                },
            ),
            "race period",
        )
        section = need(
            request(
                f"race section {attempt}",
                "admin",
                "POST",
                "/sections/",
                json={
                    "code": f"{PREFIX}-R{attempt}",
                    "description": "Cupo de concurrencia",
                    "subject_id": subject["subject_id"],
                    "teacher_id": 2,
                    "days_of_week": ["Domingo"],
                    "start_time": "06:00:00",
                    "end_time": "07:00:00",
                    "capacity": 1,
                    "room": "AUD-RACE",
                    "period_name": race_period["name"],
                },
            ),
            "race section",
        )
        barrier = Barrier(2)
        token = CLIENTS["admin"].headers["Authorization"]

        def enroll(person):
            with httpx.Client(base_url=URL, trust_env=False, timeout=40) as client:
                barrier.wait()
                response = client.post(
                    "/enrollments/",
                    headers={"Authorization": token},
                    json={
                        "student_id": person,
                        "section_id": section["section_id"],
                        "period": race_period["name"],
                    },
                )
                return {"http": response.status_code, "body": response.json()}

        with ThreadPoolExecutor(max_workers=2) as pool:
            pair = list(pool.map(enroll, [sid, second]))
        active = sum(p["body"].get("state") == "enrolled" for p in pair)
        statuses.append(
            {
                "attempt": attempt,
                "section_id": section["section_id"],
                "active": active,
                "responses": pair,
            }
        )
        record(
            f"race {attempt} accepted both selection requests",
            all(p["http"] == 200 for p in pair),
            responses=pair,
        )
        if active > 1:
            break
    record(
        "concurrent last-seat selection respects capacity",
        all(s["active"] <= 1 for s in statuses),
        attempts=statuses,
    )
    # Period identity is expected to be enforced independently of frontend controls.
    request(
        "reject selection with unknown academic period",
        "admin",
        "POST",
        "/enrollments/",
        expected=(409, 422),
        json={
            "student_id": CONTEXT["three"]["student_id"],
            "section_id": CONTEXT["sections"][2]["section_id"],
            "period": "NONEXISTENT-AUDIT",
        },
    )
    # A withdrawn user with a later hold must not be auto-promoted without validation.
    promotion_period = need(
        request(
            "promotion academic period",
            "admin",
            "POST",
            "/periods/",
            json={
                **{k: v for k, v in period.items() if k != "period_id"},
                "name": PREFIX + "-PROM",
                "active": False,
            },
        ),
        "promotion period",
    )
    section = need(
        request(
            "create promotion control section",
            "admin",
            "POST",
            "/sections/",
            json={
                "code": PREFIX + "-PROM",
                "description": "Control de promoción",
                "subject_id": subject["subject_id"],
                "teacher_id": 2,
                "days_of_week": ["Domingo"],
                "start_time": "08:00:00",
                "end_time": "09:00:00",
                "capacity": 1,
                "room": "AUD-PROM",
                "period_name": promotion_period["name"],
            },
        ),
        "promotion section",
    )
    a = need(
        request(
            "promotion control occupied seat",
            "admin",
            "POST",
            "/enrollments/",
            json={
                "student_id": sid,
                "section_id": section["section_id"],
                "period": promotion_period["name"],
            },
        ),
        "promotion first",
    )
    b = need(
        request(
            "promotion control waiting student",
            "admin",
            "POST",
            "/enrollments/",
            json={
                "student_id": second,
                "section_id": section["section_id"],
                "period": promotion_period["name"],
            },
        ),
        "promotion waiting",
    )
    request(
        "hold waiting student before promotion",
        "admin",
        "PATCH",
        f"/students/{second}",
        json={"financial_hold": True},
    )
    request(
        "release occupied promotion seat",
        "admin",
        "PATCH",
        f"/enrollments/{a['enrollment_id']}",
        json={"state": "withdrawn"},
    )
    promoted = request(
        "inspect held waiting student", "admin", "GET", f"/enrollments/{b['enrollment_id']}"
    )
    record(
        "promotion revalidates financial hold",
        promoted and promoted["state"] != "enrolled",
        state=promoted.get("state") if promoted else None,
    )
    request(
        "remove simulation hold",
        "admin",
        "PATCH",
        f"/students/{second}",
        json={"financial_hold": False},
    )


def integrity_and_restore():
    original = CONTEXT.get("original_active_period")
    if original:
        request(
            "restore demo period for UI inspection",
            "admin",
            "PATCH",
            f"/periods/{original['period_id']}",
            json={"active": True},
        )
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as db:
        result = db.execute("PRAGMA integrity_check").fetchall()
        foreign = db.execute("PRAGMA foreign_key_check").fetchall()
        record("SQLite physical integrity", result == [("ok",)], result=result)
        record("all foreign keys valid", not foreign, violations=foreign)
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        CONTEXT["table_counts"] = {
            t: db.execute('SELECT COUNT(*) FROM "' + t.replace('"', '""') + '"').fetchone()[0]
            for t in tables
        }
        record(
            "migration revision at current head",
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20261014_0032",
        )


def main():
    if not DB.is_file() or DB.resolve().parent != OUT.resolve() or URL != "http://127.0.0.2:8001":
        raise SystemExit("Refusing non-audit target")
    for name, fn in [
        ("baseline", smoke_and_scope),
        ("institutional cycle", institutional_cycle),
        ("finance and communications", finance_and_communications),
        ("edge cases", edge_cases),
        ("integrity", integrity_and_restore),
    ]:
        scenario(name, fn)
    save()
    for client in CLIENTS.values():
        client.close()
    print(
        f"AUDIT COMPLETE: {sum(c['pass'] for c in CHECKS)} passed; {sum(not c['pass'] for c in CHECKS)} failed; {OUT}"
    )


if __name__ == "__main__":
    main()
