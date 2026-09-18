import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.Session import get_db
from app.models import *  # noqa: F403 - registers all tables
from main import app
from scripts.seed_demo import seed_demo
from scripts.seed_guardian_portal import seed_guardians


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(cls.engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        cls.Session = sessionmaker(bind=cls.engine)

        def override_db():
            db = cls.Session()
            try:
                yield db
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self) -> None:
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)

    def request(self, method: str, path: str, token: str | None = None, **kwargs):
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.request(method, path, headers=headers, **kwargs)

    def bootstrap(self) -> tuple[str, dict]:
        response = self.request(
            "POST",
            "/auth/bootstrap",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "strong-password",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertNotIn("password", response.json()["user"])
        return response.json()["access_token"], response.json()["user"]

    def test_full_crud_auth_validation_and_constraints(self) -> None:
        self.assertEqual(self.request("GET", "/students/").status_code, 401)
        token, admin = self.bootstrap()
        self.assertEqual(
            self.request(
                "POST",
                "/auth/bootstrap",
                json={
                    "username": "other",
                    "email": "other@example.com",
                    "password": "password-2",
                },
            ).status_code,
            409,
        )

        login = self.request(
            "POST",
            "/auth/login",
            json={
                "username": "admin",
                "password": "strong-password",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(
            self.request("GET", "/auth/me", token=token).json()["user_id"], admin["user_id"]
        )

        career = self.request(
            "POST",
            "/careers/",
            token=token,
            json={
                "name": "Software Engineering",
                "description": "Software career",
            },
        )
        self.assertEqual(career.status_code, 200, career.text)
        career_id = career.json()["career_id"]
        self.assertEqual(
            self.request(
                "PATCH", f"/careers/{career_id}", token=token, json={"description": "Updated"}
            ).status_code,
            200,
        )

        student = self.request(
            "POST",
            "/students/",
            token=token,
            json={
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace@example.com",
                "enrollment_number": "2026-001",
                "telephone": "555-0101",
                "address": "Santo Domingo",
                "career_id": career_id,
            },
        )
        self.assertEqual(student.status_code, 200, student.text)
        student_id = student.json()["student_id"]
        self.assertEqual(
            self.request(
                "PATCH", f"/students/{student_id}", token=token, json={"telephone": "555-0111"}
            ).status_code,
            200,
        )

        teacher = self.request(
            "POST",
            "/teachers/",
            token=token,
            json={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "specialty": "Computing",
                "email": "ada@example.com",
                "telephone": "555-0102",
                "address": "Santo Domingo",
            },
        )
        self.assertEqual(teacher.status_code, 200, teacher.text)
        teacher_id = teacher.json()["teacher_id"]

        subject = self.request(
            "POST",
            "/subjects/",
            token=token,
            json={
                "code": "CS-101",
                "description": "Introduction to computing",
            },
        )
        self.assertEqual(subject.status_code, 200, subject.text)
        subject_id = subject.json()["subject_id"]

        invalid_section = self.request(
            "POST",
            "/sections/",
            token=token,
            json={
                "code": "BAD",
                "description": "Invalid",
                "teacher_id": teacher_id,
                "subject_id": subject_id,
                "days_of_week": ["Lunes"],
                "start_time": "12:00:00",
                "end_time": "10:00:00",
            },
        )
        self.assertEqual(invalid_section.status_code, 422)

        section = self.request(
            "POST",
            "/sections/",
            token=token,
            json={
                "code": "SEC-01",
                "description": "Morning section",
                "teacher_id": teacher_id,
                "subject_id": subject_id,
                "days_of_week": ["Lunes", "Miércoles"],
                "start_time": "08:00:00",
                "end_time": "10:00:00",
            },
        )
        self.assertEqual(section.status_code, 200, section.text)
        section_id = section.json()["section_id"]

        enrollment_data = {
            "student_id": student_id,
            "section_id": section_id,
            "period": "2026-3",
        }
        enrollment = self.request("POST", "/enrollments/", token=token, json=enrollment_data)
        self.assertEqual(enrollment.status_code, 200, enrollment.text)
        enrollment_id = enrollment.json()["enrollment_id"]
        self.assertEqual(
            self.request("POST", "/enrollments/", token=token, json=enrollment_data).status_code,
            409,
        )

        self.assertEqual(
            self.request(
                "POST",
                "/grades/",
                token=token,
                json={
                    "enrollment_id": enrollment_id,
                    "grade_value": 101,
                    "grade_type": "exam",
                    "date_recorded": "2026-09-15",
                },
            ).status_code,
            422,
        )
        grade = self.request(
            "POST",
            "/grades/",
            token=token,
            json={
                "enrollment_id": enrollment_id,
                "grade_value": 95,
                "grade_type": "exam",
                "date_recorded": "2026-09-15",
            },
        )
        self.assertEqual(grade.status_code, 200, grade.text)
        grade_id = grade.json()["grade_id"]
        self.assertEqual(
            self.request(
                "PATCH", f"/grades/{grade_id}", token=token, json={"grade_value": 97}
            ).status_code,
            200,
        )

        teacher_role = self.request(
            "POST",
            "/roles/",
            token=token,
            json={
                "name": "teacher",
                "description": "Teacher",
            },
        )
        self.assertEqual(teacher_role.status_code, 200, teacher_role.text)
        teacher_user = self.request(
            "POST",
            "/users/",
            token=token,
            json={
                "username": "ada",
                "email": "ada.user@example.com",
                "password": "teacher-pass",
                "role_id": teacher_role.json()["role_id"],
                "teacher_id": teacher_id,
            },
        )
        self.assertEqual(teacher_user.status_code, 200, teacher_user.text)
        self.assertNotIn("password", teacher_user.json())
        teacher_login = self.request(
            "POST",
            "/auth/login",
            json={
                "username": "ada",
                "password": "teacher-pass",
            },
        ).json()["access_token"]
        teacher_sections = self.request("GET", "/sections/", token=teacher_login)
        self.assertEqual(teacher_sections.status_code, 200, teacher_sections.text)
        self.assertEqual([item["section_id"] for item in teacher_sections.json()], [section_id])
        self.assertEqual(
            self.request(
                "GET",
                f"/academic/sections/{section_id}/workspace",
                token=teacher_login,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.request(
                "POST",
                "/careers/",
                token=teacher_login,
                json={
                    "name": "Denied",
                    "description": "Denied",
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.request(
                "PATCH", f"/grades/{grade_id}", token=teacher_login, json={"grade_value": 98}
            ).status_code,
            200,
        )
        self.assertEqual(
            len(
                self.request(
                    "GET", f"/academic/students/{student_id}/grades", token=teacher_login
                ).json()
            ),
            1,
        )
        self.assertEqual(
            len(
                self.request(
                    "GET", f"/academic/teachers/{teacher_id}/schedule", token=teacher_login
                ).json()
            ),
            1,
        )
        self.assertEqual(
            len(
                self.request(
                    "GET", f"/academic/sections/{section_id}/students", token=teacher_login
                ).json()
            ),
            1,
        )
        attendance = self.request(
            "POST",
            "/attendances/",
            token=teacher_login,
            json={"enrollment_id": enrollment_id, "present": True},
        )
        self.assertEqual(attendance.status_code, 200, attendance.text)
        attendance_id = attendance.json()["attendance_id"]
        self.assertEqual(
            self.request(
                "PATCH",
                f"/attendances/{attendance_id}",
                token=teacher_login,
                json={"present": False},
            ).status_code,
            200,
        )
        self.assertEqual(
            len(
                self.request(
                    "GET",
                    f"/attendances/?enrollment_id={enrollment_id}",
                    token=teacher_login,
                ).json()
            ),
            1,
        )
        self.assertEqual(
            self.request(
                "DELETE", f"/attendances/{attendance_id}", token=teacher_login
            ).status_code,
            200,
        )

        self.assertEqual(len(self.request("GET", "/students/", token=token).json()), 1)
        self.assertEqual(
            self.request("GET", f"/sections/{section_id}", token=token).status_code, 200
        )
        self.assertEqual(
            self.request("DELETE", f"/grades/{grade_id}", token=token).status_code, 200
        )
        self.assertEqual(
            self.request("DELETE", f"/enrollments/{enrollment_id}", token=token).status_code, 200
        )
        self.assertEqual(
            self.request("DELETE", f"/sections/{section_id}", token=token).status_code, 200
        )
        self.assertEqual(
            self.request("DELETE", f"/subjects/{subject_id}", token=token).status_code, 200
        )
        self.assertEqual(
            self.request(
                "DELETE", f"/users/{teacher_user.json()['user_id']}", token=token
            ).status_code,
            200,
        )
        self.assertEqual(
            self.request(
                "DELETE", f"/roles/{teacher_role.json()['role_id']}", token=token
            ).status_code,
            200,
        )
        self.assertEqual(
            self.request("DELETE", f"/teachers/{teacher_id}", token=token).status_code, 200
        )
        self.assertFalse(
            self.request("GET", f"/teachers/{teacher_id}", token=token).json()["active"]
        )
        self.assertEqual(
            self.request("DELETE", f"/students/{student_id}", token=token).status_code, 200
        )
        self.assertFalse(
            self.request("GET", f"/students/{student_id}", token=token).json()["active"]
        )
        # Careers with historical students are protected by the foreign key.
        self.assertEqual(
            self.request("DELETE", f"/careers/{career_id}", token=token).status_code, 409
        )

    def test_refresh_password_change_logout_and_rate_limit(self) -> None:
        token, user = self.bootstrap()
        refreshed = self.request("POST", "/auth/refresh")
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(refreshed.json()["user"]["role_name"], "admin")
        new_token = refreshed.json()["access_token"]
        changed = self.request(
            "POST",
            "/auth/change-password",
            token=new_token,
            json={"current_password": "strong-password", "new_password": "stronger-password"},
        )
        self.assertEqual(changed.status_code, 204, changed.text)
        login = self.request(
            "POST",
            "/auth/login",
            json={"username": user["username"], "password": "stronger-password"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(self.request("POST", "/auth/logout").status_code, 204)

        for _ in range(5):
            denied = self.request(
                "POST",
                "/auth/login",
                json={"username": "rate-limited-user", "password": "wrong-password"},
            )
            self.assertEqual(denied.status_code, 401)
        limited = self.request(
            "POST",
            "/auth/login",
            json={"username": "rate-limited-user", "password": "wrong-password"},
        )
        self.assertEqual(limited.status_code, 429)

    def test_academic_workspaces_and_bulk_entry(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        admin_token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        students = self.request("GET", "/students/", token=admin_token).json()
        student = next(item for item in students if item["enrollment_number"] == "DEMO-2026-001")
        sections = self.request("GET", "/sections/", token=admin_token).json()
        section = next(item for item in sections if item["code"] == "PROG-101-A")

        profile = self.request(
            "GET", f"/academic/students/{student['student_id']}/profile", token=admin_token
        )
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["career_name"], "Ingeniería de Software")

        workspace = self.request(
            "GET",
            f"/academic/sections/{section['section_id']}/workspace?attendance_date=2026-09-16",
            token=admin_token,
        )
        self.assertEqual(workspace.status_code, 200, workspace.text)
        enrollment_id = workspace.json()["roster"][0]["enrollment_id"]
        attendance = self.request(
            "POST",
            "/attendances/bulk",
            token=admin_token,
            json={
                "section_id": section["section_id"],
                "date": "2026-09-16",
                "records": [{"enrollment_id": enrollment_id, "present": True}],
            },
        )
        self.assertEqual(attendance.status_code, 200, attendance.text)
        grades = self.request(
            "POST",
            "/grades/bulk",
            token=admin_token,
            json={
                "section_id": section["section_id"],
                "grade_type": "Parcial 1",
                "date_recorded": "2026-09-16",
                "records": [{"enrollment_id": enrollment_id, "grade_value": 94}],
            },
        )
        self.assertEqual(grades.status_code, 200, grades.text)

        student_token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"},
        ).json()["access_token"]
        summary = self.request(
            "GET",
            f"/academic/students/{student['student_id']}/attendance-summary",
            token=student_token,
        )
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()[0]["percentage"], 100.0)

    def test_periods_automatic_enrollment_number_and_schedule_conflicts(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        settings = self.request(
            "PUT",
            "/configuration/institution",
            token=token,
            json={
                "institution_name": "Instituto Nexo",
                "enrollment_prefix": "NX",
                "enrollment_digits": 5,
                "passing_grade": 70,
            },
        )
        self.assertEqual(settings.status_code, 200, settings.text)
        self.assertRegex(settings.json()["enrollment_preview"], r"^NX-\d{4}-00001$")
        period = self.request(
            "POST",
            "/periods/",
            token=token,
            json={
                "name": "2027-1",
                "start_date": "2027-01-10",
                "end_date": "2027-04-30",
                "active": True,
            },
        )
        self.assertEqual(period.status_code, 200, period.text)
        career_id = self.request("GET", "/careers/", token=token).json()[0]["career_id"]
        student = self.request(
            "POST",
            "/students/",
            token=token,
            json={
                "first_name": "Ana",
                "last_name": "Pérez",
                "email": "ana.perez@example.com",
                "telephone": "809-555-0199",
                "address": "Santo Domingo",
                "career_id": career_id,
            },
        )
        self.assertEqual(student.status_code, 200, student.text)
        self.assertRegex(student.json()["enrollment_number"], r"^NX-\d{4}-00001$")

        sections = self.request("GET", "/sections/", token=token).json()
        primary = next(item for item in sections if item["code"] == "PROG-101-A")
        prerequisite_denied = self.request(
            "POST",
            "/enrollments/",
            token=token,
            json={
                "student_id": student.json()["student_id"],
                "section_id": next(item for item in sections if item["code"] == "MAT-101-B")[
                    "section_id"
                ],
                "period": "2027-1",
            },
        )
        self.assertEqual(prerequisite_denied.status_code, 409, prerequisite_denied.text)
        overlapping = self.request(
            "POST",
            "/sections/",
            token=token,
            json={
                "code": "CONFLICT-DEMO",
                "description": "Horario superpuesto",
                "teacher_id": primary["teacher_id"],
                "subject_id": primary["subject_id"],
                "days_of_week": ["Lunes"],
                "start_time": "08:30:00",
                "end_time": "10:00:00",
            },
        ).json()
        first = self.request(
            "POST",
            "/enrollments/",
            token=token,
            json={
                "student_id": student.json()["student_id"],
                "section_id": primary["section_id"],
                "period": "2027-1",
            },
        )
        self.assertEqual(first.status_code, 200, first.text)
        conflict = self.request(
            "POST",
            "/enrollments/",
            token=token,
            json={
                "student_id": student.json()["student_id"],
                "section_id": overlapping["section_id"],
                "period": "2027-1",
            },
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)

        demo_student = next(
            item
            for item in self.request("GET", "/students/", token=token).json()
            if item["enrollment_number"] == "DEMO-2026-001"
        )
        progress = self.request(
            "GET",
            f"/curriculum/students/{demo_student['student_id']}/progress",
            token=token,
        )
        self.assertEqual(progress.status_code, 200, progress.text)
        self.assertEqual(progress.json()["completed_credits"], 4.0)
        self.assertEqual(len(progress.json()["courses"]), 2)
        transcript = self.request(
            "GET",
            f"/records/students/{demo_student['student_id']}/transcript",
            token=token,
        )
        self.assertEqual(transcript.status_code, 200, transcript.text)
        self.assertGreater(transcript.json()["attempted_credits"], 0)
        self.assertIn(transcript.json()["academic_standing"], {"honors", "good", "probation"})

        dashboard = self.request("GET", "/dashboard/summary", token=token)
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(dashboard.json()["active_period"], "2027-1")
        exported = self.request("GET", "/bulk/students/export", token=token)
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertIn("DEMO-2026-001", exported.text)
        csv_content = (
            "first_name,last_name,email,telephone,address,career_id\n"
            f"Luis,Ramos,luis.ramos@example.com,809-555-0123,Santo Domingo,{career_id}\n"
        )
        imported = self.request(
            "POST",
            "/bulk/students/import",
            token=token,
            content=csv_content.encode(),
            headers={"Content-Type": "text/csv"},
        )
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["created"], 1)

        charge = self.request(
            "POST",
            f"/finance/students/{demo_student['student_id']}/charges",
            token=token,
            json={
                "description": "Matrícula del período",
                "amount": 15000,
                "due_date": "2026-09-01",
            },
        )
        self.assertEqual(charge.status_code, 200, charge.text)
        self.assertEqual(charge.json()["balance"], 15000)
        payment = self.request(
            "POST",
            f"/finance/students/{demo_student['student_id']}/payments",
            token=token,
            json={"amount": 5000, "reference": "REC-001", "note": "Pago en caja"},
        )
        self.assertEqual(payment.status_code, 200, payment.text)
        self.assertEqual(payment.json()["balance"], 10000)
        student_token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"},
        ).json()["access_token"]
        own_account = self.request(
            "GET", f"/finance/students/{demo_student['student_id']}", token=student_token
        )
        self.assertEqual(own_account.status_code, 200, own_account.text)
        self.assertEqual(len(own_account.json()["transactions"]), 2)

    def test_university_catalog_and_program_metadata(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        admin_token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.admin", "password": "NexoAdmin2026!"},
        ).json()["access_token"]
        student_token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"},
        ).json()["access_token"]

        careers = self.request("GET", "/careers/", token=admin_token)
        self.assertEqual(careers.status_code, 200, careers.text)
        program = careers.json()[0]
        self.assertEqual(program["code"], "ISW")
        self.assertEqual(program["degree_title"], "Ingeniero de Software")
        self.assertEqual(program["duration_terms"], 8)

        periods = self.request("GET", "/periods/", token=admin_token)
        self.assertEqual(periods.status_code, 200, periods.text)
        self.assertEqual(periods.json()[0]["period_type"], "semester")
        self.assertEqual(periods.json()[0]["sequence"], 1)

        catalog = self.request("GET", "/academic/catalog", token=student_token)
        self.assertEqual(catalog.status_code, 200, catalog.text)
        self.assertEqual(len(catalog.json()), 2)
        offering = catalog.json()[0]
        self.assertIn("teacher_name", offering)
        self.assertIn("available_seats", offering)
        self.assertIn("credits", offering)
        selected = next(item for item in catalog.json() if item["selection_status"] == "enrolled")
        duplicate = self.request(
            "POST",
            f"/academic/catalog/sections/{selected['section_id']}/select",
            token=student_token,
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

        denied = self.request("GET", "/academic/catalog", token=admin_token)
        self.assertEqual(denied.status_code, 403, denied.text)

    def test_weighted_assessments_and_closing_rules(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.admin", "password": "NexoAdmin2026!"},
        ).json()["access_token"]
        section = self.request("GET", "/sections/", token=token).json()[0]
        enrollment = self.request("GET", "/enrollments/", token=token).json()[0]
        assessments = []
        for name, weight in (("Prácticas", 40), ("Examen final", 60)):
            response = self.request(
                "POST",
                "/assessments/",
                token=token,
                json={"section_id": section["section_id"], "name": name, "weight": weight},
            )
            self.assertEqual(response.status_code, 200, response.text)
            assessments.append(response.json())
        overflow = self.request(
            "POST",
            "/assessments/",
            token=token,
            json={"section_id": section["section_id"], "name": "Extra", "weight": 1},
        )
        self.assertEqual(overflow.status_code, 422, overflow.text)
        for assessment, value in zip(assessments, (80, 90)):
            grades = self.request(
                "POST",
                "/grades/bulk",
                token=token,
                json={
                    "section_id": section["section_id"],
                    "assessment_id": assessment["assessment_id"],
                    "grade_type": assessment["name"],
                    "date_recorded": "2026-09-18",
                    "records": [
                        {"enrollment_id": enrollment["enrollment_id"], "grade_value": value}
                    ],
                },
            )
            self.assertEqual(grades.status_code, 200, grades.text)
            closed = self.request(
                "POST",
                f"/assessments/{assessment['assessment_id']}/close",
                token=token,
            )
            self.assertEqual(closed.status_code, 200, closed.text)
        final = self.request(
            "GET",
            f"/assessments/enrollments/{enrollment['enrollment_id']}/final",
            token=token,
        )
        self.assertEqual(final.status_code, 200, final.text)
        self.assertEqual(final.json()["weighted_grade"], 86)
        self.assertEqual(final.json()["status"], "passed")

    def test_guardians_announcements_and_private_notifications(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        admin_token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.admin", "password": "NexoAdmin2026!"},
        ).json()["access_token"]
        student = self.request("GET", "/students/", token=admin_token).json()[0]
        guardian = self.request(
            "POST",
            "/community/guardians",
            token=admin_token,
            json={
                "first_name": "Laura",
                "last_name": "Santos",
                "email": "laura.santos@example.com",
                "telephone": "809-555-0199",
                "address": "Santo Domingo",
            },
        )
        self.assertEqual(guardian.status_code, 200, guardian.text)
        link = self.request(
            "POST",
            "/community/guardian-links",
            token=admin_token,
            json={
                "student_id": student["student_id"],
                "guardian_id": guardian.json()["guardian_id"],
                "relationship": "madre",
                "primary_contact": True,
            },
        )
        self.assertEqual(link.status_code, 200, link.text)
        announcement = self.request(
            "POST",
            "/community/announcements",
            token=admin_token,
            json={"title": "Reunión", "body": "Viernes a las 4", "audience": "student"},
        )
        self.assertEqual(announcement.status_code, 200, announcement.text)
        student_token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"},
        ).json()["access_token"]
        notifications = self.request("GET", "/community/notifications", token=student_token)
        self.assertEqual(notifications.status_code, 200, notifications.text)
        self.assertEqual(notifications.json()[0]["title"], "Reunión")
        notification_id = notifications.json()[0]["notification_id"]
        marked = self.request(
            "POST", f"/community/notifications/{notification_id}/read", token=student_token
        )
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertIsNotNone(marked.json()["read_at"])
        transcript_pdf = self.request(
            "GET",
            f"/documents/students/{student['student_id']}/transcript.pdf",
            token=student_token,
        )
        self.assertEqual(transcript_pdf.status_code, 200, transcript_pdf.text)
        self.assertEqual(transcript_pdf.headers["content-type"], "application/pdf")
        self.assertTrue(transcript_pdf.content.startswith(b"%PDF-1.4"))

    def test_calendar_assignments_alerts_admissions_and_approvals(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        self.assertEqual(self.request("GET", "/health").json()["status"], "ok")
        admin_token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        teacher_token = self.request(
            "POST", "/auth/login", json={"username": "demo.docente", "password": "NexoDocente2026!"}
        ).json()["access_token"]
        student_token = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"},
        ).json()["access_token"]
        section = self.request("GET", "/sections/", token=admin_token).json()[0]
        student = self.request("GET", "/students/", token=admin_token).json()[0]
        event = self.request(
            "POST",
            "/operations/calendar",
            token=admin_token,
            json={
                "title": "Feria académica",
                "starts_at": "2026-10-10T09:00:00",
                "ends_at": "2026-10-10T12:00:00",
                "event_type": "activity",
                "audience": "all",
            },
        )
        self.assertEqual(event.status_code, 200, event.text)
        lesson = self.request(
            "POST",
            "/operations/lesson-plans",
            token=teacher_token,
            json={
                "section_id": section["section_id"],
                "scheduled_date": "2026-10-01",
                "title": "Variables",
                "content": "Conceptos y práctica",
            },
        )
        self.assertEqual(lesson.status_code, 200, lesson.text)
        assignment = self.request(
            "POST",
            "/operations/assignments",
            token=teacher_token,
            json={
                "section_id": section["section_id"],
                "title": "Ejercicio",
                "instructions": "Resolver actividad",
                "due_at": "2026-10-15T23:59:00",
                "max_score": 20,
            },
        )
        self.assertEqual(assignment.status_code, 200, assignment.text)
        submission = self.request(
            "POST",
            f"/operations/assignments/{assignment.json()['assignment_id']}/submit",
            token=student_token,
            json={"content": "Mi solución"},
        )
        self.assertEqual(submission.status_code, 200, submission.text)
        graded = self.request(
            "PATCH",
            f"/operations/submissions/{submission.json()['submission_id']}/grade",
            token=teacher_token,
            json={"score": 18, "feedback": "Buen trabajo"},
        )
        self.assertEqual(graded.status_code, 200, graded.text)
        alert = self.request(
            "POST",
            "/operations/alerts",
            token=teacher_token,
            json={
                "student_id": student["student_id"],
                "category": "academic",
                "severity": "medium",
                "reason": "Requiere seguimiento",
            },
        )
        self.assertEqual(alert.status_code, 200, alert.text)
        careers = self.request("GET", "/careers/", token=admin_token).json()
        admission = self.request(
            "POST",
            "/operations/admissions",
            token=admin_token,
            json={
                "first_name": "Paula",
                "last_name": "Pérez",
                "email": "paula.admision@example.com",
                "telephone": "809-555-0100",
                "career_id": careers[0]["career_id"],
            },
        )
        self.assertEqual(admission.status_code, 200, admission.text)
        enrolled = self.request(
            "POST",
            f"/operations/admissions/{admission.json()['admission_application_id']}/enroll",
            token=admin_token,
        )
        self.assertEqual(enrolled.status_code, 200, enrolled.text)
        approval = self.request(
            "POST",
            "/operations/approvals",
            token=teacher_token,
            json={
                "request_type": "grade_change",
                "resource_type": "submission",
                "resource_id": submission.json()["submission_id"],
                "reason": "Revisión solicitada",
            },
        )
        self.assertEqual(approval.status_code, 200, approval.text)
        resolved = self.request(
            "PATCH",
            f"/operations/approvals/{approval.json()['approval_request_id']}",
            token=admin_token,
            json={"status": "approved", "resolution_notes": "Autorizado"},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        generated = self.request("POST", "/operations/alerts/generate", token=admin_token)
        self.assertEqual(generated.status_code, 200, generated.text)
        analytics = self.request("GET", "/operations/analytics/summary", token=admin_token)
        self.assertEqual(analytics.status_code, 200, analytics.text)
        document = self.request(
            "POST",
            f"/operations/students/{student['student_id']}/documents",
            token=admin_token,
            json={
                "document_type": "identification",
                "filename": "identificacion.pdf",
                "mime_type": "application/pdf",
                "content_base64": "JVBERi0xLjQK",
            },
        )
        self.assertEqual(document.status_code, 200, document.text)
        downloaded = self.request(
            "GET",
            f"/operations/documents/{document.json()['student_document_id']}/download",
            token=admin_token,
        )
        self.assertTrue(downloaded.content.startswith(b"%PDF"))
        concept = self.request(
            "POST",
            "/finance/billing-concepts",
            token=admin_token,
            json={"name": "Laboratorio", "amount": 500, "frequency": "term"},
        )
        self.assertEqual(concept.status_code, 200, concept.text)
        permissions = self.request("GET", "/access/permissions", token=admin_token)
        self.assertEqual(permissions.status_code, 200, permissions.text)
        self.assertEqual(self.request("GET", "/access/me", token=admin_token).status_code, 200)

    def test_guardian_portal_is_limited_to_linked_students(self) -> None:
        with self.Session() as db:
            seed_demo(db)
            self.assertEqual(seed_guardians(db, limit=1), 1)
        token = self.request(
            "POST",
            "/auth/login",
            json={"username": "tutor.01", "password": "NexoTutor2026!"},
        ).json()["access_token"]
        overview = self.request("GET", "/operations/guardian/overview", token=token)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(len(overview.json()), 1)
        self.assertEqual(overview.json()[0]["enrollment_number"], "DEMO-2026-001")


if __name__ == "__main__":
    unittest.main()
