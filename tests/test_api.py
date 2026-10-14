import unittest
from datetime import time

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

    def test_subject_overview_shared_between_careers_and_delete_protection(self) -> None:
        token, _ = self.bootstrap()
        with self.Session() as db:
            seed_demo(db)
            course = db.query(CurriculumCourse).first()
            subject_id = course.subject_id
            career_id = course.career_id
            other = Career(name="Programa compartido", description="Prueba", code="COMP")
            db.add(other)
            db.commit()
            other_id = other.career_id
        added = self.request("POST", "/curriculum/courses", token, json={
            "career_id": other_id, "subject_id": subject_id, "term_number": 2,
            "credits": 4.5, "curriculum_version": "current",
        })
        self.assertEqual(added.status_code, 200, added.text)
        overview = self.request("GET", f"/subjects/{subject_id}/overview", token)
        self.assertEqual(overview.status_code, 200, overview.text)
        payload = overview.json()
        self.assertEqual({item["career_id"] for item in payload["programs"]}, {career_id, other_id})
        self.assertEqual(next(item["credits"] for item in payload["programs"] if item["career_id"] == other_id), 4.5)
        filtered = self.request("GET", "/subjects/", token, params={"career_id": other_id})
        self.assertEqual([item["subject_id"] for item in filtered.json()], [subject_id])
        self.assertTrue(payload["sections"])
        self.assertIn("teacher_name", payload["sections"][0])
        blocked = self.request("DELETE", f"/subjects/{subject_id}", token)
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(self.request("GET", f"/subjects/{subject_id}", token).status_code, 200)
        anonymous = self.request("GET", f"/subjects/{subject_id}/overview")
        self.assertEqual(anonymous.status_code, 401)

    def test_subject_validation_and_independent_catalog_lifecycle(self) -> None:
        token, _ = self.bootstrap()
        created = self.request("POST", "/subjects/", token, json={"code": " MAT-X ", "description": " Matemática "})
        self.assertEqual(created.status_code, 200, created.text)
        subject_id = created.json()["subject_id"]
        self.assertEqual(created.json()["code"], "MAT-X")
        duplicate = self.request("POST", "/subjects/", token, json={"code": "mat-x", "description": "Otra"})
        self.assertEqual(duplicate.status_code, 409)
        for values in ({"description": None}, {"code": "  "}):
            self.assertEqual(self.request("PATCH", f"/subjects/{subject_id}", token, json=values).status_code, 422)
        overview = self.request("GET", f"/subjects/{subject_id}/overview", token).json()
        self.assertEqual(overview["programs"], [])
        self.assertEqual(overview["sections"], [])
        self.assertEqual(self.request("DELETE", f"/subjects/{subject_id}", token).status_code, 200)

    def test_curriculum_links_validate_duration_duplicates_and_missing_subject(self) -> None:
        token, _ = self.bootstrap()
        with self.Session() as db:
            seed_demo(db)
            course = db.query(CurriculumCourse).first()
            course_id = course.curriculum_course_id
            values = {"career_id": course.career_id, "subject_id": course.subject_id, "term_number": 1, "credits": 3}
            duration = course.career.duration_terms
        duplicate = self.request("POST", "/curriculum/courses", token, json=values)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        missing = self.request("POST", "/curriculum/courses", token, json={**values, "subject_id": 99999})
        self.assertEqual(missing.status_code, 404)
        invalid = self.request("PATCH", f"/curriculum/courses/{course_id}", token, json={"term_number": duration + 1})
        self.assertEqual(invalid.status_code, 422)
        invalid_null = self.request("PATCH", f"/curriculum/courses/{course_id}", token, json={"credits": None})
        self.assertEqual(invalid_null.status_code, 422)

    def test_career_catalog_fields_filters_and_version_scoped_offer(self) -> None:
        token, _ = self.bootstrap()
        with self.Session() as db:
            seed_demo(db)
            career = db.query(Career).first()
            career_id = career.career_id
            code = career.code
            courses = db.query(CurriculumCourse).filter_by(career_id=career_id).all()
            for course in courses:
                course.curriculum_version = "2026"
            career.curriculum_version = "2026"
            db.commit()
        fields = {
            "faculty": "Escuela de Tecnología", "coordinator_name": "Elena Demo",
            "modality": "hybrid", "status": "suspended",
            "graduate_profile": "Resuelve problemas con ética y calidad.",
            "admission_requirements": "Bachillerato concluido.",
            "contact_email": "coordinacion@example.com",
        }
        saved = self.request("PATCH", f"/careers/{career_id}", token, json=fields)
        self.assertEqual(saved.status_code, 200, saved.text)
        for key, value in fields.items():
            self.assertEqual(saved.json()[key], value)
        matches = self.request("GET", "/careers/", token, params={"q": code, "status": "suspended", "modality": "hybrid"})
        self.assertEqual([row["career_id"] for row in matches.json()], [career_id])
        self.assertEqual(self.request("GET", "/careers/", token, params={"status": "active"}).json(), [])
        self.assertEqual(self.request("GET", "/careers/catalog-options", token).json()["faculties"], [fields["faculty"]])
        self.assertEqual(self.request("PATCH", f"/careers/{career_id}", token, json={"status": None}).status_code, 422)
        self.assertEqual(self.request("PATCH", f"/careers/{career_id}", token, json={"contact_email": "bad"}).status_code, 422)
        self.assertIsNone(self.request("PATCH", f"/careers/{career_id}", token, json={"coordinator_name": None}).json()["coordinator_name"])
        overview = self.request("GET", f"/careers/{career_id}/overview", token).json()
        self.assertEqual(overview["active_students"], 1)
        self.assertGreater(len(overview["sections"]), 0)
        empty = self.request("GET", f"/careers/{career_id}/overview", token, params={"version": "other"}).json()
        self.assertEqual(empty["sections"], [])
        self.assertEqual(self.request("GET", f"/careers/{career_id}/overview").status_code, 401)
        created = self.request("POST", "/careers/", token, json={
            "code": "POS-TEST", "name": "Programa de prueba", "description": "Catálogo institucional",
            "academic_level": "postgraduate", "status": "draft", "modality": "virtual",
            "faculty": "Escuela de Postgrado", "graduate_profile": "Perfil ficticio de egreso",
        })
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["status"], "draft")
        filtered = self.request("GET", "/careers/", token, params={"academic_level": "postgraduate", "faculty": "Escuela de Postgrado"}).json()
        self.assertEqual([item["code"] for item in filtered], ["POS-TEST"])
        student_login = self.request("POST", "/auth/login", json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"})
        student_token = student_login.json()["access_token"]
        self.assertEqual(self.request("GET", f"/careers/{career_id}/overview", student_token).status_code, 403)
        self.assertEqual(self.request("PATCH", f"/careers/{career_id}", student_token, json={"status": "active"}).status_code, 403)

    def test_teacher_dossier_filters_workload_and_access(self) -> None:
        token, _ = self.bootstrap()
        with self.Session() as db:
            seed_demo(db)
            teacher = db.query(Teacher).first()
            teacher_id = teacher.teacher_id
            sections = (
                db.query(Section)
                .filter_by(teacher_id=teacher_id)
                .order_by(Section.section_id)
                .all()
            )
            for section in sections:
                section.period_name = "DEMO-2026"
                for enrollment in section.enrollments:
                    enrollment.period = "DEMO-2026"
            sections[0].status = "published"
            sections[1].status = "closed"
            db.add(
                SectionMeeting(
                    section_id=sections[0].section_id,
                    day_of_week="Lunes",
                    start_time=time(8),
                    end_time=time(10),
                )
            )
            db.commit()
        updated = self.request(
            "PATCH",
            f"/teachers/{teacher_id}",
            token=token,
            json={
                "employee_code": "DOC-TEST-001",
                "document_number": "DEMO-TEACHER",
                "academic_degree": "Maestría en Educación",
                "alma_mater": "Universidad ficticia",
                "experience_years": 12,
                "department": "Tecnología",
                "teaching_category": "Titular",
                "employment_type": "full_time",
                "appointment_date": "2020-08-17",
                "emergency_contact_name": "Contacto ficticio",
                "emergency_contact_phone": "555-0100",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["assigned_sections"], 1)
        other = self.request(
            "POST",
            "/teachers/",
            token=token,
            json={
                "first_name": "Otra",
                "last_name": "Docente",
                "specialty": "Ciencias",
                "email": "other-teacher@example.com",
                "telephone": "555-0200",
                "address": "Dirección ficticia",
                "active": False,
                "employment_type": "part_time",
            },
        )
        self.assertEqual(other.status_code, 200, other.text)
        listed = self.request(
            "GET",
            "/teachers/",
            token=token,
            params={
                "q": "DOC-TEST",
                "department": "Tecnología",
                "active": "true",
                "employment_type": "full_time",
                "limit": 1,
            },
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["teacher_id"] for item in listed.json()], [teacher_id])
        self.assertEqual(
            self.request("GET", "/teachers/departments", token=token).json(), ["Tecnología"]
        )
        self.assertEqual(
            self.request("GET", "/teachers/", token=token, params={"skip": 2}).json(), []
        )
        self.assertEqual(
            self.request("GET", "/teachers/", token=token, params={"active": "false"}).json()[0][
                "teacher_id"
            ],
            other.json()["teacher_id"],
        )
        cleared = self.request(
            "PATCH", f"/teachers/{teacher_id}", token=token, json={"emergency_contact_phone": None}
        )
        self.assertIsNone(cleared.json()["emergency_contact_phone"])
        self.assertEqual(cleared.json()["academic_degree"], "Maestría en Educación")
        self.assertEqual(
            self.request(
                "PATCH", f"/teachers/{teacher_id}", token=token, json={"experience_years": -1}
            ).status_code,
            422,
        )
        load = self.request(
            "GET", f"/teachers/{teacher_id}/workload", token=token, params={"period": "DEMO-2026"}
        )
        self.assertEqual(load.status_code, 200, load.text)
        self.assertEqual(load.json()["unique_students"], 1)
        self.assertEqual(load.json()["active_sections"], 1)
        self.assertEqual(load.json()["scheduled_weekly_hours"], 2)
        self.assertEqual(len(load.json()["sections"]), 2)
        self.assertEqual(len(load.json()["sections"][0]["meetings"]), 1)
        with self.Session() as db:
            section = db.query(Section).filter_by(teacher_id=teacher_id, status="closed").one()
            section.status = "published"
            db.commit()
        expanded = self.request(
            "GET", f"/teachers/{teacher_id}/workload", token=token, params={"period": "DEMO-2026"}
        ).json()
        self.assertEqual(expanded["active_sections"], 2)
        self.assertEqual(expanded["unique_students"], 1)
        self.assertEqual(expanded["scheduled_weekly_hours"], 5)
        self.assertEqual(
            self.request(
                "GET", f"/teachers/{teacher_id}/workload", token=token, params={"period": "OTHER"}
            ).json()["sections"],
            [],
        )
        login = self.request(
            "POST", "/auth/login", json={"username": "demo.docente", "password": "NexoDocente2026!"}
        )
        self.assertEqual(login.status_code, 200, login.text)
        teacher_token = login.json()["access_token"]
        self.assertEqual(len(self.request("GET", "/teachers/", token=teacher_token).json()), 1)
        self.assertEqual(
            self.request(
                "GET", f"/teachers/{other.json()['teacher_id']}/workload", token=teacher_token
            ).status_code,
            403,
        )
        self.assertEqual(self.request("GET", f"/teachers/{teacher_id}/workload").status_code, 401)
        self.assertEqual(
            self.request("GET", "/teachers/99999/workload", token=token).status_code, 404
        )

    def test_student_dossier_and_combined_directory_filters(self) -> None:
        token, _ = self.bootstrap()
        career = self.request(
            "POST",
            "/careers/",
            token=token,
            json={
                "name": "Dossier test program",
                "description": "Test curriculum",
            },
        ).json()
        base = {
            "first_name": "Ana",
            "last_name": "Prueba",
            "telephone": "555-0100",
            "address": "Dirección ficticia",
            "career_id": career["career_id"],
        }
        created = self.request(
            "POST",
            "/students/",
            token=token,
            json={
                **base,
                "email": "dossier@example.com",
                "document_number": "TEST-DOC-24",
                "birth_date": "2005-02-12",
                "nationality": "Dominicana",
                "admission_date": "2026-09-01",
                "previous_school": "Centro ficticio",
                "emergency_contact_name": "Contacto ficticio",
                "emergency_contact_phone": "555-0200",
                "emergency_contact_relationship": "Madre",
                "academic_hold": True,
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        student_id = created.json()["student_id"]
        second = self.request(
            "POST",
            "/students/",
            token=token,
            json={
                **base,
                "email": "other-dossier@example.com",
                "active": False,
            },
        )
        self.assertEqual(second.status_code, 200, second.text)
        filtered = self.request(
            "GET",
            "/students/",
            token=token,
            params={
                "career_id": career["career_id"],
                "active": "true",
                "hold": "academic",
                "q": "TEST-DOC",
                "limit": 1,
            },
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual([item["student_id"] for item in filtered.json()], [student_id])
        profile = self.request("GET", f"/academic/students/{student_id}/profile", token=token)
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["birth_date"], "2005-02-12")
        self.assertTrue(profile.json()["academic_hold"])
        self.assertEqual(profile.json()["emergency_contact_name"], "Contacto ficticio")
        patched = self.request(
            "PATCH",
            f"/students/{student_id}",
            token=token,
            json={
                "emergency_contact_phone": None,
            },
        )
        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertIsNone(patched.json()["emergency_contact_phone"])
        self.assertEqual(patched.json()["document_number"], "TEST-DOC-24")
        self.assertEqual(
            self.request(
                "GET",
                "/students/",
                token=token,
                params={
                    "active": "false",
                    "hold": "clear",
                },
            ).json()[0]["student_id"],
            second.json()["student_id"],
        )
        self.assertEqual(
            self.request(
                "GET",
                "/students/",
                token=token,
                params={
                    "hold": "invalid",
                },
            ).status_code,
            422,
        )
        self.assertEqual(self.request("GET", "/students/").status_code, 401)

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
                "PATCH", f"/grades/{grade_id}", token=token, json={"grade_value": 97, "reason": "Corrección verificada"}
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
                "PATCH", f"/grades/{grade_id}", token=teacher_login, json={"grade_value": 98, "reason": "Corrección docente"}
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
                json={"present": False, "reason": "Corrección del pase de lista"},
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
            self.request("DELETE", f"/grades/{grade_id}", token=token, json={"reason": "Anulación de prueba"}).status_code, 200
        )
        self.assertEqual(
            self.request("DELETE", f"/enrollments/{enrollment_id}", token=token).status_code, 409
        )
        self.assertEqual(
            self.request("DELETE", f"/sections/{section_id}", token=token).status_code, 409
        )
        self.assertEqual(
            self.request("DELETE", f"/subjects/{subject_id}", token=token).status_code, 409
        )
        self.assertEqual(
            self.request(
                "DELETE", f"/users/{teacher_user.json()['user_id']}", token=token
            ).status_code,
            409,
        )
        self.assertEqual(
            self.request(
                "DELETE", f"/roles/{teacher_role.json()['role_id']}", token=token
            ).status_code,
            409,
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
        self.assertIn("selectable", offering)
        selection_summary = self.request("GET", "/academic/catalog/summary", token=student_token)
        self.assertEqual(selection_summary.status_code, 200, selection_summary.text)
        self.assertEqual(selection_summary.json()["selected_credits"], 7.0)
        self.assertGreater(selection_summary.json()["maximum_credits"], 0)
        selected = next(item for item in catalog.json() if item["selection_status"] == "enrolled")
        duplicate = self.request(
            "POST",
            f"/academic/catalog/sections/{selected['section_id']}/select",
            token=student_token,
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

        denied = self.request("GET", "/academic/catalog", token=admin_token)
        self.assertEqual(denied.status_code, 403, denied.text)

        summaries = self.request("GET", "/academic/sections/academic-summary", token=admin_token)
        self.assertEqual(summaries.status_code, 200, summaries.text)
        self.assertEqual(len(summaries.json()), 2)
        programming = next(
            item for item in summaries.json() if item["section_code"] == "PROG-101-A"
        )
        self.assertEqual(programming["student_count"], 1)
        self.assertIsNotNone(programming["attendance_percentage"])
        self.assertIsNotNone(programming["grade_average"])

        student_denied = self.request(
            "GET", "/academic/sections/academic-summary", token=student_token
        )
        self.assertEqual(student_denied.status_code, 403, student_denied.text)

    def grading_fixture(self):
        with self.Session() as db:
            seed_demo(db)
            section = db.query(Section).first()
            enrollment = db.query(Enrollment).filter_by(section_id=section.section_id).first()
            ids = section.section_id, enrollment.enrollment_id, enrollment.student_id
        admin = self.request("POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}).json()["access_token"]
        student = self.request("POST", "/auth/login", json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"}).json()["access_token"]
        return admin, student, *ids

    def test_draft_privacy_zero_and_consistent_weighted_results(self):
        admin, student, section_id, enrollment_id, student_id = self.grading_fixture()
        items = [self.request("POST", "/assessments/", admin, json={"section_id": section_id, "name": name, "weight": weight}).json() for name, weight in (("Parcial", 20), ("Proyecto", 80))]
        for item, value in zip(items, (0, 90)):
            response = self.request("POST", "/grades/bulk", admin, json={"section_id": section_id, "assessment_id": item["assessment_id"], "grade_type": item["name"], "date_recorded": "2026-10-12", "status": "draft", "records": [{"enrollment_id": enrollment_id, "grade_value": value}]})
            self.assertEqual(response.status_code, 200, response.text)
            item["grade_id"] = response.json()[0]["grade_id"]
            self.assertEqual(self.request("GET", f"/grades/{item['grade_id']}", student).status_code, 404)
            self.assertEqual(self.request("POST", f"/assessments/{item['assessment_id']}/close", admin).status_code, 409)
        final_path = f"/assessments/enrollments/{enrollment_id}/final"
        self.assertEqual(self.request("GET", final_path, student).json()["completed_weight"], 0)
        progress = self.request("GET", f"/curriculum/students/{student_id}/progress", student).json()
        self.assertEqual(progress["completed_credits"], 0)
        for item in items:
            self.assertEqual(self.request("POST", f"/grades/assessments/{item['assessment_id']}/publish", admin).status_code, 200)
        provisional = self.request("GET", final_path, student).json()
        self.assertEqual(provisional["weighted_grade"], 72)
        self.assertFalse(provisional["final"])
        for item in items:
            self.assertEqual(self.request("POST", f"/assessments/{item['assessment_id']}/close", admin).status_code, 200)
        final = self.request("GET", final_path, student).json()
        self.assertEqual(final["status"], "passed")
        transcript = self.request("GET", f"/records/students/{student_id}/transcript", student).json()
        self.assertEqual(next(row["average"] for row in transcript["courses"] if row["section_code"] == self.request("GET", f"/sections/{section_id}", admin).json()["code"]), 72)
        progress = self.request("GET", f"/curriculum/students/{student_id}/progress", student).json()
        self.assertEqual(progress["courses"][0]["final_average"], 72)
        history = self.request("GET", f"/grades/{items[0]['grade_id']}/history", admin)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["action"], "published")

    def test_rename_distribution_transaction_and_grade_annulment(self):
        admin, _, section_id, enrollment_id, _ = self.grading_fixture()
        items = [self.request("POST", "/assessments/", admin, json={"section_id": section_id, "name": name, "weight": weight}).json() for name, weight in (("Examen", 40), ("Práctica", 60))]
        payload = {"section_id": section_id, "assessment_id": items[0]["assessment_id"], "grade_type": "Examen", "date_recorded": "2026-10-12", "records": [{"enrollment_id": enrollment_id, "grade_value": 70}]}
        grade_id = self.request("POST", "/grades/bulk", admin, json=payload).json()[0]["grade_id"]
        renamed = self.request("PATCH", f"/assessments/{items[0]['assessment_id']}", admin, json={"name": "Examen renombrado"})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        saved = self.request("POST", "/grades/bulk", admin, json={**payload, "records": [{"enrollment_id": enrollment_id, "grade_value": 80}]})
        self.assertEqual(saved.json()[0]["grade_id"], grade_id)
        distribution = {"reason": "Redistribución aprobada", "components": [{"assessment_id": item["assessment_id"], "weight": 50} for item in items]}
        updated = self.request("PATCH", f"/assessments/sections/{section_id}/distribution", admin, json=distribution)
        self.assertEqual(updated.status_code, 200, updated.text)
        distribution["components"][0]["weight"] = 60
        self.assertEqual(self.request("PATCH", f"/assessments/sections/{section_id}/distribution", admin, json=distribution).status_code, 422)
        self.assertEqual([item["weight"] for item in self.request("GET", f"/assessments/sections/{section_id}", admin).json()], [50, 50])
        duplicate = self.request("POST", "/grades/bulk", admin, json={**payload, "records": payload["records"] * 2})
        self.assertEqual(duplicate.status_code, 422)
        self.assertEqual(self.request("PATCH", f"/grades/{grade_id}", admin, json={"assessment_id": items[1]["assessment_id"], "reason": "Intento de traslado"}).status_code, 422)
        self.assertEqual(self.request("DELETE", f"/grades/{grade_id}", admin, json={"reason": "Anulación justificada"}).status_code, 200)
        history = self.request("GET", f"/grades/{grade_id}/history", admin).json()
        self.assertEqual(history[0]["action"], "voided")
        with self.Session() as db:
            self.assertEqual(db.query(Grade).filter_by(assessment_id=items[0]["assessment_id"]).count(), 1)
            self.assertEqual(db.get(Grade, grade_id).status, "voided")

    def test_subject_plan_templates_copy_without_overwriting(self):
        admin, _, section_id, _, _ = self.grading_fixture()
        with self.Session() as db:
            section = db.get(Section, section_id)
            subject_id = section.subject_id
            new = Section(code="PLAN-COPY", description="Copia", teacher_id=section.teacher_id, subject_id=subject_id,
                days_of_week=section.days_of_week, start_time=section.start_time, end_time=section.end_time)
            db.add(new)
            db.commit()
            copy_id = new.section_id
        payload = {"name": "Esquema regular", "subject_id": subject_id, "components": [{"name": "Parcial", "weight": 30}, {"name": "Proyecto", "weight": 70}]}
        template = self.request("POST", "/assessments/plans/templates", admin, json=payload)
        self.assertEqual(template.status_code, 200, template.text)
        teacher = self.request("POST", "/auth/login", json={"username": "demo.docente", "password": "NexoDocente2026!"}).json()["access_token"]
        visible = self.request("GET", "/assessments/plans/templates", teacher, params={"subject_id": subject_id})
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(len(visible.json()), 1)
        path = f"/assessments/plans/templates/{template.json()['assessment_template_id']}/apply"
        copied = self.request("POST", path, teacher, json={"section_id": copy_id})
        self.assertEqual(copied.status_code, 200, copied.text)
        self.assertEqual(sum(item["weight"] for item in copied.json()), 100)
        self.assertEqual(self.request("POST", path, teacher, json={"section_id": copy_id}).status_code, 409)
        self.assertEqual(len(self.request("GET", f"/assessments/sections/{section_id}", admin).json()), 0)

    def test_period_lock_and_reopen_audit(self):
        admin, _, section_id, enrollment_id, _ = self.grading_fixture()
        item = self.request("POST", "/assessments/", admin, json={"section_id": section_id, "name": "Única", "weight": 100}).json()
        saved = self.request("POST", "/grades/bulk", admin, json={"section_id": section_id, "assessment_id": item["assessment_id"], "grade_type": "Única", "date_recorded": "2026-10-12", "status": "published", "records": [{"enrollment_id": enrollment_id, "grade_value": 85}]}).json()[0]
        with self.Session() as db:
            # Waiting and withdrawn selections must not prevent closing.
            db.add(Enrollment(student_id=db.get(Enrollment, enrollment_id).student_id, section_id=section_id, period="WAIT-TEST", state="waitlisted"))
            db.commit()
        self.assertEqual(self.request("POST", f"/assessments/{item['assessment_id']}/close", admin).status_code, 200)
        self.assertEqual(self.request("POST", f"/assessments/{item['assessment_id']}/reopen", admin, json={"reason": "Revisión autorizada"}).status_code, 200)
        audit = self.request("GET", f"/assessments/sections/{section_id}/audit", admin).json()
        self.assertTrue(any(row["action"] == "assessment.reopened" for row in audit))
        with self.Session() as db:
            period = db.query(AcademicPeriod).filter_by(name=db.get(Enrollment, enrollment_id).period).one()
            period.status = "closed"
            db.commit()
        self.assertEqual(self.request("POST", f"/grades/assessments/{item['assessment_id']}/publish", admin).status_code, 409)
        self.assertEqual(self.request("PATCH", f"/grades/{saved['grade_id']}", admin, json={"grade_value": 90, "reason": "Corrección"}).status_code, 409)
        self.assertEqual(self.request("POST", "/assessments/", admin, json={"section_id": section_id, "name": "Otra", "weight": 1}).status_code, 409)
        with self.Session() as db:
            period = db.query(AcademicPeriod).filter_by(name=db.get(Enrollment, enrollment_id).period).one()
            period.status = "active"
            section = db.get(Section, section_id)
            section.status = "closed"
            db.get(Enrollment, enrollment_id).state = "completed"
            db.get(Assessment, item["assessment_id"]).closed = True
            db.commit()
        reopened = self.request("POST", f"/assessments/{item['assessment_id']}/reopen", admin, json={"reason": "Corrección histórica autorizada"})
        self.assertEqual(reopened.status_code, 200, reopened.text)
        roster = self.request("GET", f"/academic/sections/{section_id}/workspace", admin).json()["roster"]
        self.assertEqual(len(roster), 1)
        corrected = self.request("PATCH", f"/grades/{saved['grade_id']}", admin, json={"grade_value": 90, "reason": "Corrección histórica"})
        self.assertEqual(corrected.status_code, 200, corrected.text)

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
                    "status": "published",
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

    def test_equivalences_career_history_and_graduation_audit(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        admin_token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        student_login = self.request(
            "POST",
            "/auth/login",
            json={"username": "demo.estudiante", "password": "NexoEstudiante2026!"},
        ).json()
        student_token = student_login["access_token"]
        student_id = student_login["user"]["student_id"]
        career = self.request("GET", "/careers/", token=admin_token).json()[0]
        subjects = self.request("GET", "/subjects/", token=admin_token).json()
        equivalence = self.request(
            "POST",
            "/governance/equivalences",
            token=admin_token,
            json={
                "career_id": career["career_id"],
                "source_subject_id": subjects[0]["subject_id"],
                "target_subject_id": subjects[1]["subject_id"],
                "curriculum_version": career["curriculum_version"],
                "notes": "Reconocimiento de prueba",
            },
        )
        self.assertEqual(equivalence.status_code, 200, equivalence.text)
        audit = self.request(
            "GET", f"/governance/students/{student_id}/graduation-audit", token=student_token
        )
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertEqual(len(audit.json()["requirements"]), 2)
        second_career = self.request(
            "POST",
            "/careers/",
            token=admin_token,
            json={
                "code": "ADM-TEST",
                "name": "Administración de prueba",
                "description": "Programa alternativo",
                "degree_title": "Licenciado de prueba",
                "required_credits": 120,
            },
        )
        self.assertEqual(second_career.status_code, 200, second_career.text)
        changed = self.request(
            "POST",
            f"/governance/students/{student_id}/career-change",
            token=admin_token,
            json={
                "new_career_id": second_career.json()["career_id"],
                "effective_date": "2026-09-21",
                "reason": "Solicitud académica aprobada",
            },
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        history = self.request(
            "GET", f"/governance/students/{student_id}/career-history", token=student_token
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()), 1)

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

    def test_section_followup_consistent_population_and_published_contributions(self):
        tokens, section = self.task_fixture()
        with self.Session() as db:
            enrollment = db.query(Enrollment).filter_by(section_id=section).first()
            enrollment.state = "completed"
            assessment = Assessment(section_id=section, name="Parcial de seguimiento", weight=40, closed=False)
            other = Assessment(section_id=section, name="Final de seguimiento", weight=60, closed=False)
            db.add_all([assessment, other])
            db.flush()
            published = Grade(enrollment_id=enrollment.enrollment_id, assessment_id=assessment.assessment_id, grade_type=assessment.name, grade_value=80, date_recorded="2026-10-12", status="published")
            draft = Grade(enrollment_id=enrollment.enrollment_id, assessment_id=other.assessment_id, grade_type=other.name, grade_value=90, date_recorded="2026-10-12", status="draft")
            db.add_all([published, draft])
            db.commit()
            enrollment_id = enrollment.enrollment_id
            draft_id = draft.grade_id
        summaries = self.request("GET", "/academic/sections/academic-summary", tokens["teacher"])
        self.assertEqual(summaries.status_code, 200, summaries.text)
        summary = next(s for s in summaries.json() if s["section_id"] == section)
        workspace = self.request("GET", f"/academic/sections/{section}/workspace", tokens["teacher"])
        self.assertEqual(workspace.status_code, 200, workspace.text)
        row = next(s for s in workspace.json()["roster"] if s["enrollment_id"] == enrollment_id)
        self.assertEqual(summary["student_count"], len(workspace.json()["roster"]))
        self.assertEqual(summary["grade_average"], 32)
        self.assertEqual(summary["graded_student_count"], 1)
        self.assertEqual(summary["pending_student_count"], 1)
        self.assertEqual(summary["final_student_count"], 0)
        self.assertEqual(summary["draft_grade_count"], 1)
        self.assertEqual(summary["assessment_count"], 2)
        self.assertEqual(summary["configured_weight"], 100)
        self.assertEqual(row["completed_weight"], 40)
        self.assertEqual(row["average_grade"], 32)
        notes = {g["status"]: g for g in row["grades"] if g["assessment_id"] is not None}
        self.assertEqual(notes["published"]["assessment_weight"], 40)
        self.assertEqual(notes["published"]["contribution"], 32)
        self.assertIsNone(notes["draft"]["contribution"])
        with self.Session() as db:
            db.get(Grade, draft_id).status = "voided"
            db.get(Enrollment, enrollment_id).state = "withdrawn"
            db.commit()
        summary = next(s for s in self.request("GET", "/academic/sections/academic-summary", tokens["teacher"]).json() if s["section_id"] == section)
        self.assertEqual(summary["student_count"], 0)
        self.assertIsNone(summary["grade_average"])
        self.assertEqual(self.request("GET", f"/academic/sections/{section}/workspace", tokens["teacher"]).json()["roster"], [])
        self.assertEqual(self.request("GET", "/academic/sections/academic-summary", tokens["student"]).status_code, 403)

    def test_attendance_explicit_states_counts_and_audited_boolean_correction(self):
        tokens, section = self.task_fixture()
        with self.Session() as db:
            db.get(Section, section).days_of_week = "Lunes, Miércoles"
            db.query(SectionMeeting).filter_by(section_id=section).delete()
            enrollment_id = db.query(Enrollment).filter_by(section_id=section).first().enrollment_id
            db.commit()
        session = self.request("GET", f"/attendances/sections/{section}/session", tokens["teacher"], params={"day": "2026-09-21"})
        self.assertEqual(session.status_code, 200, session.text)
        self.assertIsNone(session.json()["roster"][0]["status"])
        self.assertEqual(self.request("GET", f"/attendances/sections/{section}/session", tokens["student"]).status_code, 403)
        blank = self.request("POST", "/attendances/bulk", tokens["teacher"], json={"section_id": section, "date": "2026-09-21", "records": [{"enrollment_id": enrollment_id}]})
        self.assertEqual(blank.status_code, 422)
        records = []
        for day, status in (("2026-09-21", "present"), ("2026-09-23", "late"), ("2026-09-28", "early_departure"), ("2026-09-30", "excused"), ("2026-10-05", "absent")):
            response = self.request("POST", "/attendances/bulk", tokens["teacher"], json={"section_id": section, "date": day, "records": [{"enrollment_id": enrollment_id, "status": status, "note": "Certificado médico" if status == "excused" else ""}]})
            self.assertEqual(response.status_code, 200, response.text)
            records.append(response.json()[0])
        student_id = self.request("GET", "/students/", tokens["admin"]).json()[0]["student_id"]
        params = {"start": "2026-09-21", "end": "2026-10-05"}
        student = next(r for r in self.request("GET", f"/academic/students/{student_id}/attendance-summary", tokens["student"], params=params).json() if r["enrollment_id"] == enrollment_id)
        self.assertEqual((student["present_count"], student["total_count"], student["percentage"]), (3, 5, 60))
        self.assertEqual(student["counts"], {"present": 1, "absent": 1, "late": 1, "excused": 1, "early_departure": 1})
        self.assertEqual(len(student["records"]), 5)
        summary = next(r for r in self.request("GET", "/academic/sections/academic-summary", tokens["teacher"], params=params).json() if r["section_id"] == section)
        self.assertEqual((summary["attendance_total"], summary["attendance_percentage"]), (5, 60))
        correction = self.request("PATCH", f"/attendances/{records[1]['attendance_id']}", tokens["teacher"], json={"present": False, "reason": "No asistió; corregir tardanza"})
        self.assertEqual(correction.status_code, 200, correction.text)
        self.assertEqual((correction.json()["present"], correction.json()["status"]), (False, "absent"))
        history = self.request("GET", f"/attendances/{records[1]['attendance_id']}/history", tokens["teacher"])
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["previous"]["status"], "late")
        self.assertEqual(history.json()[0]["current"]["status"], "absent")
        self.assertEqual(len(history.json()), 2)
        self.assertEqual(self.request("GET", f"/attendances/{records[1]['attendance_id']}/history", tokens["student"]).status_code, 403)

    def test_attendance_identity_atomicity_and_validation(self):
        tokens, section = self.task_fixture()
        with self.Session() as db:
            db.get(Section, section).days_of_week = "Lunes, Miércoles"
            db.query(SectionMeeting).filter_by(section_id=section).delete()
            enrollment_id = db.query(Enrollment).filter_by(section_id=section).first().enrollment_id
            db.commit()
        body = {"section_id": section, "date": "2026-09-21", "reason": "Pase de lista", "records": [{"enrollment_id": enrollment_id, "status": "present"}]}
        duplicate = {**body, "records": body["records"] * 2}
        self.assertEqual(self.request("POST", "/attendances/bulk", tokens["teacher"], json=duplicate).status_code, 422)
        wrong = {**body, "records": body["records"] + [{"enrollment_id": 999999, "status": "absent"}]}
        self.assertEqual(self.request("POST", "/attendances/bulk", tokens["teacher"], json=wrong).status_code, 422)
        record = self.request("POST", "/attendances/bulk", tokens["teacher"], json=body)
        self.assertEqual(record.status_code, 200, record.text)
        record_id = record.json()[0]["attendance_id"]
        body["records"][0]["status"] = "excused"
        self.assertEqual(self.request("POST", "/attendances/bulk", tokens["teacher"], json=body).status_code, 422)
        self.assertEqual(self.request("GET", f"/attendances/{record_id}", tokens["teacher"]).json()["status"], "present")
        self.assertEqual(self.request("POST", "/attendances/", tokens["teacher"], json={"enrollment_id": enrollment_id, "date": "2026-09-21T18:00:00", "present": True}).status_code, 409)
        body["records"][0]["status"] = "absent"
        response = self.request("POST", "/attendances/bulk", tokens["teacher"], json=body)
        self.assertEqual(response.json()[0]["attendance_id"], record_id)
        future = {**body, "date": "2099-01-01"}
        self.assertEqual(self.request("POST", "/attendances/bulk", tokens["teacher"], json=future).status_code, 422)
        self.assertEqual(self.request("PATCH", f"/attendances/{record_id}", tokens["teacher"], json={"status": None, "reason": "Corrección"}).status_code, 422)
        self.assertEqual(self.request("PATCH", f"/attendances/{record_id}", tokens["teacher"], json={"status": "present"}).status_code, 422)
        from sqlalchemy.exc import IntegrityError
        from datetime import datetime
        with self.Session() as db:
            db.add(Attendance(enrollment_id=enrollment_id, date=datetime(2026, 9, 21, 20), present=True, status="present"))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()
        self.assertEqual(self.request("GET", "/attendances/", tokens["teacher"], params={"start": "2026-10-05", "end": "2026-09-01"}).status_code, 422)

    def test_attendance_schedule_exception_and_closed_period(self):
        tokens, section = self.task_fixture()
        with self.Session() as db:
            db.get(Section, section).days_of_week = "Lunes, Miércoles"
            db.query(SectionMeeting).filter_by(section_id=section).delete()
            enrollment_id = db.query(Enrollment).filter_by(section_id=section).first().enrollment_id
            db.commit()
        body = {"section_id": section, "date": "2026-09-22", "records": [{"enrollment_id": enrollment_id, "status": "present"}], "reason": "Clase extraordinaria"}
        self.assertEqual(self.request("POST", "/attendances/bulk", tokens["teacher"], json=body).status_code, 422)
        self.assertEqual(self.request("POST", "/attendances/bulk", tokens["admin"], json=body).status_code, 422)
        body["exception_reason"] = "Recuperación autorizada de clase"
        saved = self.request("POST", "/attendances/bulk", tokens["admin"], json=body)
        self.assertEqual(saved.status_code, 200, saved.text)
        record_id = saved.json()[0]["attendance_id"]
        with self.Session() as db:
            db.get(Enrollment, enrollment_id).state = "completed"
            db.commit()
        self.assertEqual(self.request("PATCH", f"/attendances/{record_id}", tokens["teacher"], json={"status": "late", "reason": "Llegó después"}).status_code, 200)
        body["date"] = "2026-09-23"
        self.assertEqual(self.request("POST", "/attendances/bulk", tokens["admin"], json=body).status_code, 409)
        with self.Session() as db:
            db.query(AcademicPeriod).first().status = "closed"
            db.commit()
        self.assertEqual(self.request("PATCH", f"/attendances/{record_id}", tokens["admin"], json={"status": "present", "reason": "Corregir"}).status_code, 409)

    def test_equivalence_consistency_impact_history_and_permissions(self):
        tokens, _ = self.task_fixture()
        with self.Session() as db:
            student = db.query(Student).first()
            sid, career_id = student.student_id, student.career_id
            source = db.query(Subject).filter_by(code="PROG-101").one().subject_id
            target = db.query(Subject).filter_by(code="MAT-101").one().subject_id
            version = student.career.curriculum_version
            grades_before = db.query(Grade).count()
        body = dict(career_id=career_id, source_subject_id=source, target_subject_id=target,
                    curriculum_version=version, reason="Reconocimiento curricular", notes="Prueba")
        path = "/governance/equivalences"
        preview = self.request("POST", path + "/preview", tokens["admin"], json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["affected_students"], 1)
        self.assertEqual(preview.json()["students"][0]["credit_delta"], 3)
        self.assertEqual(self.request("GET", path, tokens["admin"]).json(), [])
        for role in ("student", "teacher"):
            self.assertEqual(self.request("POST", path, tokens[role], json=body).status_code, 403)
        created = self.request("POST", path, tokens["admin"], json=body)
        self.assertEqual(created.status_code, 200, created.text)
        rid = created.json()["course_equivalence_id"]
        self.assertEqual(self.request("POST", path, tokens["admin"], json=body).status_code, 409)
        invalid = dict(body, curriculum_version="inexistente")
        self.assertEqual(self.request("POST", path + "/preview", tokens["admin"], json=invalid).status_code, 422)
        cycle = dict(body, source_subject_id=target, target_subject_id=source)
        self.assertEqual(self.request("POST", path, tokens["admin"], json=cycle).status_code, 409)
        progress = self.request("GET", f"/curriculum/students/{sid}/progress", tokens["student"]).json()
        record = self.request("GET", f"/records/students/{sid}/transcript", tokens["student"]).json()
        audit = self.request("GET", f"/governance/students/{sid}/graduation-audit", tokens["student"]).json()
        self.assertEqual(progress["completed_credits"], 7)
        self.assertEqual(record["earned_credits"], audit["earned_credits"])
        self.assertEqual(record["earned_credits"], progress["completed_credits"])
        self.assertEqual(record["cumulative_average"], 92)
        recognized = next(c for c in record["courses"] if c["result"] == "recognized")
        self.assertIsNone(recognized["average"])
        self.assertEqual(recognized["attempts"], 0)
        self.assertEqual(recognized["origin_subject_code"], "PROG-101")
        self.assertEqual(recognized["equivalence_ids"], [rid])
        self.assertIsNone(next(c for c in progress["courses"] if c["subject_id"] == target)["final_average"])
        impact = self.request("GET", f"{path}/{rid}/impact", tokens["admin"], params={"active": False})
        self.assertEqual(impact.status_code, 200, impact.text)
        self.assertEqual(impact.json()["students"][0]["credit_delta"], -3)
        edit = self.request("PATCH", f"{path}/{rid}", tokens["admin"], json={"active": False, "notes": "Suspendida", "reason": "Revisión del comité"})
        self.assertEqual(edit.status_code, 200, edit.text)
        history = self.request("GET", f"{path}/{rid}/history", tokens["admin"]).json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["action"], "equivalence.deactivated")
        self.assertEqual(history[0]["actor"], "demo.admin")
        self.assertEqual(self.request("GET", f"/curriculum/students/{sid}/progress", tokens["student"]).json()["completed_credits"], 4)
        with self.Session() as db:
            self.assertEqual(db.query(Grade).count(), grades_before)

    def test_equivalence_chains_versions_prerequisites_and_no_double_credit(self):
        from app.services.academic_recognition import recognize
        from app.services.enrollment_service import create_enrollment_service
        from app.schemas.enrollment_schema import EnrollmentCreate
        from fastapi import HTTPException
        tokens, _ = self.task_fixture()
        with self.Session() as db:
            student = db.query(Student).first()
            origin = db.query(Subject).filter_by(code="PROG-101").one()
            target = db.query(Subject).filter_by(code="MAT-101").one()
            third = Subject(code="TER-101", description="Materia avanzada")
            fourth = Subject(code="CUA-101", description="Materia con requisito")
            db.add_all([third, fourth])
            db.flush()
            for subject in (third, fourth):
                db.add(CurriculumCourse(career_id=student.career_id, subject_id=subject.subject_id, term_number=3, credits=2, curriculum_version=student.career.curriculum_version, prerequisite_subject_id=target.subject_id, corequisite_subject_id=third.subject_id if subject == fourth else None))
            # Insert the downstream rule first: closure must not depend on ID ordering.
            db.add(CourseEquivalence(career_id=student.career_id, source_subject_id=target.subject_id, target_subject_id=third.subject_id, curriculum_version=student.career.curriculum_version))
            db.flush()
            db.add(CourseEquivalence(career_id=student.career_id, source_subject_id=origin.subject_id, target_subject_id=target.subject_id, curriculum_version=student.career.curriculum_version))
            db.flush()
            db.add(CourseEquivalence(career_id=student.career_id, source_subject_id=origin.subject_id, target_subject_id=fourth.subject_id, curriculum_version="histórica"))
            section = Section(code="CUA-A", description="Avanzada", teacher_id=db.query(Teacher).first().teacher_id, subject_id=fourth.subject_id, days_of_week="Viernes", start_time=time(14), end_time=time(15), status="active")
            db.add(section)
            db.commit()
            db.refresh(student)
            recognition = recognize(db, student)
            self.assertIn(third.subject_id, recognition.completed)
            self.assertNotIn(fourth.subject_id, recognition.completed)
            self.assertEqual(len(recognition.paths[third.subject_id]), 2)
            enrollment = create_enrollment_service(db, EnrollmentCreate(student_id=student.student_id, section_id=section.section_id, period="2026-2027"))
            self.assertEqual(enrollment.state, "enrolled")
            target_section = db.query(Section).filter_by(subject_id=target.subject_id).one()
            with self.assertRaises(HTTPException) as rejected:
                create_enrollment_service(db, EnrollmentCreate(student_id=student.student_id, section_id=target_section.section_id, period="2026-2027"))
            self.assertEqual(rejected.exception.status_code, 409)
            # Direct approval takes priority over a rule; no duplicate recognized row or credit.
            target_enrollment = db.query(Enrollment).filter_by(student_id=student.student_id, section_id=target_section.section_id).one()
            db.add(Grade(enrollment_id=target_enrollment.enrollment_id, grade_type="Final", grade_value=80, date_recorded="2026-09-20", status="published"))
            db.commit()
            recognition = recognize(db, student)
            self.assertNotIn(target.subject_id, recognition.paths)
            self.assertIn(target.subject_id, recognition.direct)
            sid = student.student_id
        record = self.request("GET", f"/records/students/{sid}/transcript", tokens["student"])
        self.assertEqual(record.status_code, 200, record.text)
        self.assertEqual(record.json()["earned_credits"], 9)
        self.assertEqual(record.json()["recognized_credits"], 2)

    def test_equivalence_inactive_cycle_invalid_destination_and_draft_source(self):
        tokens, _ = self.task_fixture()
        with self.Session() as db:
            student = db.query(Student).first()
            sid = student.student_id
            source = db.query(Subject).filter_by(code="PROG-101").one().subject_id
            target = db.query(Subject).filter_by(code="MAT-101").one().subject_id
            outside = Subject(code="OUT-101", description="Fuera del pensum")
            db.add(outside)
            db.commit()
            body = dict(career_id=student.career_id, source_subject_id=source, target_subject_id=target, curriculum_version=student.career.curriculum_version, reason="Regla del comité")
            invalid = dict(body, target_subject_id=outside.subject_id)
        path = "/governance/equivalences"
        self.assertEqual(self.request("POST", path, tokens["admin"], json=invalid).status_code, 422)
        first = self.request("POST", path, tokens["admin"], json=body)
        self.assertEqual(first.status_code, 200, first.text)
        inverse = self.request("POST", path, tokens["admin"], json=dict(body, source_subject_id=target, target_subject_id=source, active=False))
        self.assertEqual(inverse.status_code, 200, inverse.text)
        rid = inverse.json()["course_equivalence_id"]
        self.assertEqual(self.request("GET", f"{path}/{rid}/impact", tokens["admin"], params={"active": True}).status_code, 409)
        self.assertEqual(self.request("PATCH", f"{path}/{rid}", tokens["admin"], json={"active": True, "notes": "", "reason": "Activar"}).status_code, 409)
        self.assertEqual(len(self.request("GET", path, tokens["admin"], params={"active": False}).json()), 1)
        with self.Session() as db:
            db.query(Grade).first().status = "draft"
            db.commit()
        progress = self.request("GET", f"/curriculum/students/{sid}/progress", tokens["student"]).json()
        self.assertEqual(progress["completed_credits"], 0)

    def finance_fixture(self, amount="1000.01"):
        tokens, _ = self.task_fixture()
        with self.Session() as db:
            sid = db.query(Student).first().student_id
        base = f"/finance/students/{sid}"
        response = self.request("POST", base + "/charges", tokens["admin"], json={"description": "Mensualidad", "amount": amount, "due_date": "2020-01-01"})
        self.assertEqual(response.status_code, 200, response.text)
        return tokens, sid, base

    def test_finance_cents_audit_reversal_and_idempotency(self):
        tokens, sid, base = self.finance_fixture()
        for amount in ("0", "-1", "1.001", "Infinity", "1000000000"):
            invalid = self.request("POST", base + "/payments", tokens["admin"], json={"amount": amount, "reference": "INVALIDA"})
            self.assertEqual(invalid.status_code, 422, invalid.text)
        body = {"amount": "100.01", "reference": "EFECTIVO-001", "idempotency_key": "operacion-001"}
        first = self.request("POST", base + "/payments", tokens["admin"], json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["balance"], 900)
        self.assertEqual(self.request("POST", base + "/payments", tokens["admin"], json=body).json()["balance"], 900)
        self.assertEqual(self.request("POST", base + "/payments", tokens["admin"], json=dict(body, amount="101")).status_code, 409)
        self.assertEqual(self.request("POST", base + "/payments", tokens["admin"], json=dict(body, idempotency_key="otra-clave")).status_code, 409)
        adjustment = self.request("POST", base + "/adjustments", tokens["admin"], json={"kind": "scholarship", "description": "Beca aprobada", "amount": "200"})
        self.assertEqual(adjustment.status_code, 200, adjustment.text)
        self.assertEqual(adjustment.json()["balance"], 700)
        self.assertEqual(adjustment.json()["overdue_balance"], 700)
        self.assertEqual(self.request("GET", "/operations/analytics/summary", tokens["admin"]).json()["receivables"], 700)
        self.assertEqual({t["type"] for t in adjustment.json()["transactions"]}, {"charge", "payment", "adjustment"})
        payment = next(t for t in first.json()["transactions"] if t["type"] == "payment")
        receipt = self.request("GET", f"/finance/payments/{payment['transaction_id']}/receipt.pdf", tokens["student"])
        self.assertEqual(receipt.status_code, 200, receipt.text)
        self.assertEqual(receipt.headers["content-type"], "application/pdf")
        reversal = self.request("POST", f"{base}/transactions/payment/{payment['transaction_id']}/reverse", tokens["admin"], json={"reason": "Registro equivocado"})
        self.assertEqual(reversal.status_code, 200, reversal.text)
        self.assertEqual(reversal.json()["balance"], 800.01)
        self.assertEqual(next(t for t in reversal.json()["transactions"] if t["type"] == "payment")["status"], "reversed")
        self.assertEqual(self.request("POST", f"{base}/transactions/payment/{payment['transaction_id']}/reverse", tokens["admin"], json={"reason": "Repetido"}).status_code, 409)
        history = self.request("GET", base + "/history", tokens["admin"]).json()
        self.assertEqual(len(history), 4)
        self.assertTrue(all(h["actor"] == "demo.admin" for h in history))
        with self.Session() as db:
            self.assertEqual(db.query(Payment).count(), 1)
            self.assertEqual(db.query(FinanceEvent).filter_by(student_id=sid).count(), 4)

    def test_finance_transfers_private_proof_manual_approval_and_rejection(self):
        import base64
        from unittest.mock import patch
        from app.db.database import settings
        tokens, sid, base = self.finance_fixture()
        body = {"amount": "250", "reference": "BANCO-001", "bank": "Banco de pruebas", "proof_base64": base64.b64encode(b"%PDF-1.4\ncomprobante ficticio").decode()}
        with patch.object(settings, "finance_transfer_instructions", ""):
            self.assertEqual(self.request("POST", base + "/transfers", tokens["student"], json=body).status_code, 409)
        with patch.object(settings, "finance_transfer_instructions", "Cuenta ficticia exclusiva de pruebas"):
            invalid = self.request("POST", base + "/transfers", tokens["student"], json=dict(body, proof_base64=base64.b64encode(b"archivo exe").decode()))
            self.assertEqual(invalid.status_code, 422)
            submitted = self.request("POST", base + "/transfers", tokens["student"], json=body)
            self.assertEqual(submitted.status_code, 200, submitted.text)
            rid = submitted.json()["transfer_request_id"]
            self.assertEqual(self.request("GET", base, tokens["student"]).json()["balance"], 1000.01)
            self.assertEqual(self.request("POST", base + "/transfers", tokens["student"], json=body).status_code, 409)
            self.assertEqual(self.request("GET", f"/finance/transfers/{rid}/proof", tokens["teacher"]).status_code, 403)
            proof = self.request("GET", f"/finance/transfers/{rid}/proof", tokens["student"])
            self.assertEqual(proof.content, b"%PDF-1.4\ncomprobante ficticio")
            self.assertEqual(proof.headers["cache-control"], "no-store")
            review_body = {"approve": True, "reason": "Ingreso confirmado en banco"}
            self.assertEqual(self.request("POST", f"/finance/transfers/{rid}/review", tokens["student"], json=review_body).status_code, 403)
            approved = self.request("POST", f"/finance/transfers/{rid}/review", tokens["admin"], json=review_body)
            self.assertEqual(approved.status_code, 200, approved.text)
            self.assertEqual(approved.json()["status"], "approved")
            self.assertEqual(self.request("POST", f"/finance/transfers/{rid}/review", tokens["admin"], json=review_body).status_code, 409)
            self.assertEqual(self.request("GET", base, tokens["student"]).json()["balance"], 750.01)
            second = self.request("POST", base + "/transfers", tokens["student"], json=dict(body, reference="BANCO-002")).json()["transfer_request_id"]
            rejected = self.request("POST", f"/finance/transfers/{second}/review", tokens["admin"], json={"approve": False, "reason": "Comprobante no verificable"})
            self.assertEqual(rejected.json()["status"], "rejected")
            self.assertEqual(self.request("GET", base, tokens["student"]).json()["balance"], 750.01)
        with self.Session() as db:
            self.assertEqual(db.query(Payment).count(), 1)

    def test_finance_monthly_plans_partial_credits_cancel_and_no_duplicate_debt(self):
        from app.services.finance_workflow import business_date
        tokens, _, base = self.finance_fixture()
        first = f"{business_date().year + 1}-01-31"
        created = self.request("POST", base + "/payment-plans", tokens["admin"], json={"name": "Plan mensual", "installments": 3, "first_due_date": first})
        self.assertEqual(created.status_code, 200, created.text)
        pid = created.json()["payment_plan_id"]
        duplicate = self.request("POST", base + "/payment-plans", tokens["admin"], json={"name": "Duplicado", "installments": 2, "first_due_date": first})
        self.assertEqual(duplicate.status_code, 409)
        items = self.request("GET", base + "/payment-plans", tokens["student"]).json()[0]["installments"]
        self.assertEqual(round(sum(i["amount"] for i in items), 2), 1000.01)
        self.assertIn(items[1]["due_date"][-5:], ("02-28", "02-29"))
        self.assertTrue(items[2]["due_date"].endswith("03-31"))
        paid = self.request("POST", base + "/payments", tokens["admin"], json={"amount": "100", "reference": "PLAN-001"})
        self.assertEqual(paid.status_code, 200, paid.text)
        items = self.request("GET", base + "/payment-plans", tokens["student"]).json()[0]["installments"]
        self.assertEqual(items[0]["paid_amount"], 100)
        self.assertEqual(items[0]["status"], "partial")
        self.request("POST", base + "/adjustments", tokens["admin"], json={"kind": "discount", "description": "Descuento académico", "amount": "233.34"})
        items = self.request("GET", base + "/payment-plans", tokens["student"]).json()[0]["installments"]
        self.assertEqual(items[0]["status"], "paid")
        cancelled = self.request("POST", f"{base}/payment-plans/{pid}/cancel", tokens["admin"], json={"reason": "Reprogramar compromisos"})
        self.assertEqual(cancelled.status_code, 200)
        self.request("POST", base + "/payments", tokens["admin"], json={"amount": "10", "reference": "PLAN-002"})
        frozen = self.request("GET", base + "/payment-plans", tokens["student"]).json()[0]
        self.assertFalse(frozen["active"])
        self.assertEqual(frozen["installments"][1]["paid_amount"], 0)
        self.assertEqual(self.request("GET", base, tokens["student"]).json()["balance"], 656.67)

    def test_finance_closed_cash_and_simulator_never_posts_real_money(self):
        from app.services.finance_workflow import business_date
        tokens, _, base = self.finance_fixture()
        paid = self.request("POST", base + "/payments", tokens["admin"], json={"amount": "100", "reference": "CIERRE-001"})
        self.assertEqual(paid.status_code, 200, paid.text)
        payment_id = next(t for t in paid.json()["transactions"] if t["type"] == "payment")["transaction_id"]
        today = business_date().isoformat()
        closing = self.request("POST", f"/finance/cash-closings/{today}", tokens["admin"])
        self.assertEqual(closing.status_code, 200, closing.text)
        self.assertEqual(closing.json()["cash_total"], 100)
        blocked = self.request("POST", base + "/payments", tokens["admin"], json={"amount": "50", "reference": "CIERRE-002"})
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(self.request("POST", f"{base}/transactions/payment/{payment_id}/reverse", tokens["admin"], json={"reason": "Intento fuera de cierre"}).status_code, 409)
        for outcome in ("approved", "declined", "cancelled"):
            simulated = self.request("POST", base + "/simulate", tokens["admin"], json={"amount": "100", "outcome": outcome})
            self.assertEqual(simulated.status_code, 200, simulated.text)
            self.assertFalse(simulated.json()["balance_changed"])
        self.assertEqual(self.request("POST", base + "/simulate", tokens["student"], json={"amount": "1", "outcome": "approved"}).status_code, 403)
        self.assertEqual(self.request("GET", base, tokens["student"]).json()["balance"], 900.01)
        with self.Session() as db:
            self.assertEqual(db.query(Payment).count(), 1)

    def test_finance_read_only_empty_accounts_and_cross_student_access(self):
        tokens, _ = self.task_fixture()
        with self.Session() as db:
            student = db.query(Student).first()
            sid = student.student_id
            other = Student(first_name="Otra", last_name="Persona", enrollment_number="OTRA-001", email="otra@example.test", telephone="8095550101", address="Pruebas", career_id=student.career_id)
            db.add(other)
            db.commit()
            other_id = other.student_id
        self.assertEqual(self.request("GET", "/finance/accounts", tokens["admin"]).status_code, 200)
        self.assertEqual(self.request("GET", f"/finance/students/{sid}", tokens["student"]).json()["balance"], 0)
        self.assertEqual(self.request("GET", f"/finance/students/{other_id}", tokens["student"]).status_code, 403)
        with self.Session() as db:
            self.assertEqual(db.query(StudentAccount).count(), 0)
            self.assertEqual(db.query(FinanceControl).count(), 0)

    def test_communications_scoped_preview_delivery_retry_and_read_provenance(self):
        tokens, section = self.task_fixture()
        body = {"title": "Aviso de sección", "body": "Recordatorio académico", "audience": "section", "section_id": section, "delivery_key": "publicacion-001"}
        self.assertEqual(self.request("POST", "/community/announcements", tokens["teacher"], json=dict(body, audience="all", section_id=None)).status_code, 403)
        preview = self.request("POST", "/community/announcements/preview", tokens["teacher"], json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["count"], 1)
        self.assertEqual(self.request("GET", "/community/notifications", tokens["student"]).json(), [])
        body["expected_recipients"] = preview.json()["fingerprint"]
        created = self.request("POST", "/community/announcements", tokens["teacher"], json=body)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["delivery_count"], 1)
        self.assertEqual(self.request("POST", "/community/announcements", tokens["teacher"], json=body).json()["announcement_id"], created.json()["announcement_id"])
        self.assertEqual(self.request("POST", "/community/announcements", tokens["teacher"], json=dict(body, body="Texto diferente")).status_code, 409)
        notices = self.request("GET", "/community/notifications", tokens["student"]).json()
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["announcement_id"], created.json()["announcement_id"])
        path = f"/community/notifications/{notices[0]['notification_id']}/read"
        first = self.request("POST", path, tokens["student"]).json()["read_at"]
        self.assertEqual(self.request("POST", path, tokens["student"]).json()["read_at"], first)
        self.assertEqual(self.request("POST", path, tokens["teacher"]).status_code, 404)
        self.assertEqual(self.request("GET", "/community/announcements", tokens["teacher"]).json()[0]["read_count"], 1)
        self.assertEqual(self.request("POST", "/community/notifications/read-all", tokens["student"]).json()["marked"], 0)
        with self.Session() as db:
            db.query(Enrollment).filter_by(section_id=section).one().state = "waitlisted"
            db.commit()
        empty = dict(body, delivery_key="publicacion-002", expected_recipients=None)
        self.assertEqual(self.request("POST", "/community/announcements/preview", tokens["teacher"], json=empty).json()["count"], 0)
        self.assertEqual(self.request("POST", "/community/announcements", tokens["teacher"], json=empty).status_code, 409)

    def test_communications_guardians_and_stale_recipient_preview(self):
        from app.security import hash_password
        tokens, section = self.task_fixture()
        with self.Session() as db:
            student = db.query(Student).first()
            role = Role(name="guardian", description="Tutor")
            guardian = Guardian(first_name="Tutora", last_name="Prueba", email="tutora@example.test", telephone="8095550100")
            db.add_all([role, guardian])
            db.flush()
            db.add(StudentGuardian(student_id=student.student_id, guardian_id=guardian.guardian_id, relationship="madre"))
            db.add(User(username="tutora.prueba", email="tutora.login@example.test", password=hash_password("PruebaTutor2026!"), role_id=role.role_id, guardian_id=guardian.guardian_id))
            db.commit()
        body = {"title":"Reunión con tutores", "body":"Revisar seguimiento", "audience":"section_guardians", "section_id":section, "delivery_key":"aviso-tutores-001"}
        preview = self.request("POST", "/community/announcements/preview", tokens["teacher"], json=body).json()
        self.assertEqual(preview["count"], 1)
        self.assertEqual(preview["roles"]["guardian"], 1)
        created = self.request("POST", "/community/announcements", tokens["teacher"], json=dict(body, expected_recipients=preview["fingerprint"]))
        self.assertEqual(created.status_code, 200, created.text)
        with self.Session() as db:
            db.query(Enrollment).filter_by(section_id=section).one().state = "withdrawn"
            db.commit()
        stale = self.request("POST", "/community/announcements", tokens["teacher"], json=dict(body, audience="section", delivery_key="aviso-tutores-002", expected_recipients=preview["fingerprint"]))
        self.assertEqual(stale.status_code, 409)
        with self.Session() as db:
            self.assertEqual(db.query(Announcement).count(), 1)
            self.assertEqual(db.query(Notification).count(), 1)

    def test_configuration_preserves_existing_threshold_and_rejects_stale_edits(self):
        from app.services.academic_grading import academic_result
        tokens, _ = self.task_fixture()
        current = self.request("GET", "/configuration/institution", tokens["admin"]).json()
        body = {k: current[k] for k in ("institution_name","enrollment_prefix","enrollment_digits","passing_grade","max_credits_per_period")}
        body.update(passing_grade=95, reason="Nuevo criterio para futuras selecciones", expected_revision=current["revision"])
        preview = self.request("POST", "/configuration/institution/preview", tokens["admin"], json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["existing_selections_preserved"], 2)
        saved = self.request("PUT", "/configuration/institution", tokens["admin"], json=body)
        self.assertEqual(saved.status_code, 200, saved.text)
        with self.Session() as db:
            enrollment = db.query(Enrollment).join(Section).join(Subject).filter(Subject.code=="PROG-101").one()
            self.assertEqual(enrollment.passing_grade, 70)
            self.assertEqual(academic_result(db,enrollment).status,"passed")
            from app.repositories.enrollment_repository import create_enrollment
            from app.schemas.enrollment_schema import EnrollmentCreate
            future = create_enrollment(db, EnrollmentCreate(student_id=enrollment.student_id, section_id=enrollment.section_id, period="2030"))
            self.assertEqual(future.passing_grade, 95)
            db.add(Grade(enrollment_id=future.enrollment_id, grade_type="Final", grade_value=92, date_recorded="2030-01-01"))
            db.commit()
            self.assertEqual(academic_result(db,future).status,"failed")
        self.assertEqual(self.request("PUT", "/configuration/institution", tokens["admin"], json=dict(body, institution_name="Otro nombre")).status_code, 409)
        self.assertEqual(len(self.request("GET", "/configuration/institution/history", tokens["admin"]).json()), 1)
        self.assertEqual(self.request("PUT", "/configuration/institution", tokens["student"], json=body).status_code, 403)
        self.request("POST", "/operations/alerts/generate", tokens["admin"])
        with self.Session() as db:
            self.assertEqual(db.query(EarlyAlert).filter_by(category="academic").count(), 1)

    def test_admissions_controlled_atomic_transition_and_retry(self):
        from unittest.mock import patch
        from fastapi import HTTPException
        tokens, _ = self.task_fixture()
        with self.Session() as db:
            career = db.query(Career).first().career_id
        created = self.request("POST", "/operations/admissions", tokens["admin"], json={"first_name":"Nueva","last_name":"Solicitud","email":"solicitud.control@example.com","telephone":"8095550101","career_id":career})
        self.assertEqual(created.status_code, 200, created.text)
        path = f"/operations/admissions/{created.json()['admission_application_id']}"
        self.assertEqual(self.request("POST", path+"/enroll", tokens["admin"]).status_code, 409)
        self.assertEqual(self.request("PATCH", path, tokens["admin"], json={"status":"enrolled"}).status_code, 409)
        self.assertEqual(self.request("PATCH", path, tokens["admin"], json={"status":"accepted"}).status_code, 409)
        self.assertEqual(self.request("PATCH", path, tokens["admin"], json={"status":"review", "expected_status":"submitted"}).status_code, 200)
        self.assertEqual(self.request("PATCH", path, tokens["admin"], json={"status":"accepted", "expected_status":"submitted"}).status_code, 409)
        self.assertEqual(self.request("PATCH", path, tokens["admin"], json={"status":"accepted"}).status_code, 200)
        with patch("app.services.student_service.create_student", side_effect=HTTPException(409,"Fallo de prueba controlado")):
            self.assertEqual(self.request("POST", path+"/enroll", tokens["admin"]).status_code, 409)
        with self.Session() as db:
            self.assertEqual(db.query(Student).count(), 1)
            self.assertEqual(db.query(AdmissionApplication).one().status, "accepted")
        first = self.request("POST", path+"/enroll", tokens["admin"])
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.request("POST", path+"/enroll", tokens["admin"]).json(), first.json())
        self.assertEqual(self.request("PATCH", path, tokens["admin"], json={"status":"review"}).status_code, 409)
        self.assertEqual(self.request("POST", path+"/enroll", tokens["teacher"]).status_code, 403)
        self.assertEqual(len(self.request("GET", path+"/history", tokens["admin"]).json()), 4)

    def test_period_close_requires_published_grades_and_restores_only_changed_states(self):
        tokens, section = self.task_fixture()
        with self.Session() as db:
            period = db.query(AcademicPeriod).first()
            pid = period.period_id
            for item in db.query(Section):
                item.period_name = period.name
                assessment = Assessment(section_id=item.section_id, name="Final controlada", weight=100, closed=True)
                db.add(assessment)
                db.flush()
                enrollment = db.query(Enrollment).filter_by(section_id=item.section_id).one()
                db.add(Grade(enrollment_id=enrollment.enrollment_id, assessment_id=assessment.assessment_id, grade_type="Final controlada", grade_value=80, date_recorded="2026-10-01", status="draft"))
            db.commit()
        path = f"/periods/{pid}"
        self.assertFalse(self.request("GET", path+"/closing-preview", tokens["admin"]).json()["can_close"])
        self.assertEqual(self.request("POST", path+"/close", tokens["admin"]).status_code, 409)
        with self.Session() as db:
            for grade in db.query(Grade).filter(Grade.assessment_id.is_not(None)):
                grade.status = "published"
            independent = db.query(Section).filter(Section.section_id!=section).one()
            independent.status = "closed"
            independent_id = independent.section_id
            db.commit()
        closed = self.request("POST", path+"/close", tokens["admin"], json={"reason":"Cierre revisado y autorizado"})
        self.assertEqual(closed.status_code, 200, closed.text)
        with self.Session() as db:
            self.assertTrue(all(e.state=="completed" for e in db.query(Enrollment)))
        self.assertEqual(self.request("POST", path+"/reopen", tokens["admin"], json={"reason":"Corrección autorizada"}).status_code, 200)
        with self.Session() as db:
            self.assertEqual(db.get(Section, section).status, "published")
            self.assertEqual(db.get(Section, independent_id).status, "closed")
            self.assertTrue(all(e.state=="enrolled" for e in db.query(Enrollment)))
            self.assertTrue(all(a.closed for a in db.query(Assessment)))
        self.assertEqual(self.request("PATCH", path, tokens["admin"], json={"name":"RENOMBRADO"}).status_code, 409)
        self.assertEqual(self.request("DELETE", path, tokens["admin"]).status_code, 409)

    def test_period_dates_permission_safety_and_empty_analytics(self):
        tokens, _ = self.task_fixture()
        invalid = self.request("POST", "/periods/", tokens["admin"], json={"name":"Fechas inválidas","start_date":"2030-01-01","end_date":"2030-06-01","registration_start":"2030-02-01","registration_end":"2030-01-01"})
        self.assertEqual(invalid.status_code, 422)
        valid = self.request("POST", "/periods/", tokens["admin"], json={"name":"Sin resultados","start_date":"2030-01-01","end_date":"2030-06-01"})
        self.assertEqual(valid.status_code, 200, valid.text)
        metrics = self.request("GET", "/operations/analytics/academic", tokens["admin"], params={"period":"Sin resultados"})
        self.assertEqual(metrics.status_code, 200, metrics.text)
        self.assertTrue(all(m["average_grade"] is None and m["pass_rate"] is None for m in metrics.json()["subject_metrics"]))
        with self.Session() as db:
            role = db.query(Role).filter_by(name="admin").one()
            rid = role.role_id
            for slug in ("access.manage","academic.manage"):
                permission = Permission(slug=slug, description=slug)
                db.add(permission)
                db.flush()
                db.add(RolePermission(role_id=rid, permission_id=permission.permission_id))
            db.commit()
        path = f"/access/roles/{rid}/permissions"
        self.assertEqual(self.request("PUT", path, tokens["admin"], json={"permissions":["academic.manage"], "reason":"Prueba de protección"}).status_code, 409)
        self.assertEqual(self.request("PUT", path, tokens["admin"], json={"permissions":["access.manage"], "reason":"Prueba de protección"}).status_code, 409)
        self.assertEqual(self.request("PUT", path, tokens["admin"], json={"permissions":["access.manage","academic.manage"], "expected_permissions":[], "reason":"Edición desactualizada"}).status_code, 409)
        with self.Session() as db:
            admin_id = db.query(User).filter_by(username="demo.admin").one().user_id
            teacher_role = db.query(Role).filter_by(name="teacher").one().role_id
        self.assertEqual(self.request("DELETE", f"/users/{admin_id}", tokens["admin"]).status_code, 409)
        self.assertEqual(self.request("PATCH", f"/users/{admin_id}", tokens["admin"], json={"role_id":teacher_role}).status_code, 409)

    def task_fixture(self):
        with self.Session() as db:
            seed_demo(db)
        tokens = {}
        for role, username, password in (("admin", "demo.admin", "NexoAdmin2026!"), ("teacher", "demo.docente", "NexoDocente2026!"), ("student", "demo.estudiante", "NexoEstudiante2026!")):
            tokens[role] = self.request("POST", "/auth/login", json={"username": username, "password": password}).json()["access_token"]
        section = self.request("GET", "/sections/", tokens["admin"]).json()[0]
        return tokens, section["section_id"]

    def test_task_drafts_policies_attempts_and_roster(self):
        tokens, section = self.task_fixture()
        body = {"section_id": section, "title": "Actividad organizada", "instructions": "Resolver y explicar", "due_at": "2099-01-01T23:00:00-04:00", "published": False, "max_score": 20}
        response = self.request("POST", "/operations/assignments", tokens["teacher"], json=body)
        self.assertEqual(response.status_code, 200, response.text)
        task_id = response.json()["assignment_id"]
        path = f"/operations/assignments/{task_id}"
        self.assertEqual(self.request("GET", "/operations/assignments", tokens["student"], params={"section_id": section}).json(), [])
        self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Intento"}).status_code, 404)
        body["published"] = True
        self.assertEqual(self.request("PUT", path, tokens["teacher"], json=body).status_code, 200)
        first = self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Primera solución"})
        self.assertEqual(first.status_code, 200, first.text)
        sub_id = first.json()["submission_id"]
        second = self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Segunda solución"})
        self.assertEqual(second.json()["attempts"], 2)
        history = self.request("GET", f"/operations/submissions/{sub_id}/revisions", tokens["student"])
        self.assertEqual([r["content"] for r in history.json()], ["Primera solución", "Segunda solución"])
        roster = self.request("GET", f"{path}/submissions", tokens["teacher"])
        self.assertEqual(roster.status_code, 200, roster.text)
        self.assertIn("student_name", roster.json()[0])
        self.assertEqual(self.request("GET", f"{path}/submissions", tokens["student"]).status_code, 403)
        self.assertEqual(self.request("POST", "/operations/assignments", tokens["student"], json=body).status_code, 403)
        self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": " "}).status_code, 422)
        graded = self.request("PATCH", f"/operations/submissions/{sub_id}/grade", tokens["teacher"], json={"score": 0, "feedback": "Revisar fundamentos"})
        self.assertEqual(graded.status_code, 200, graded.text)
        own = self.request("GET", "/operations/assignments", tokens["student"]).json()[0]
        self.assertEqual(own["submission"]["score"], 0)
        self.assertEqual(own["submission"]["feedback"], "Revisar fundamentos")
        self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Otra"}).status_code, 409)
        body["max_score"] = 50
        self.assertEqual(self.request("PUT", path, tokens["teacher"], json=body).status_code, 409)

    def test_task_deadline_lifecycle_and_active_enrollment(self):
        tokens, section = self.task_fixture()
        body = {"section_id": section, "title": "Fuera de plazo", "instructions": "Resolver actividad", "due_at": "2000-01-01T00:00:00Z"}
        task = self.request("POST", "/operations/assignments", tokens["teacher"], json=body).json()
        path = f"/operations/assignments/{task['assignment_id']}"
        self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Solución"}).status_code, 409)
        body["allow_late"] = True
        self.assertEqual(self.request("PUT", path, tokens["teacher"], json=body).status_code, 200)
        self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Solución tardía"}).status_code, 200)
        for lifecycle in ("closed", "archived"):
            body["lifecycle"] = lifecycle
            self.assertEqual(self.request("PUT", path, tokens["teacher"], json=body).status_code, 200)
            self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Reenvío"}).status_code, 409)
        body["lifecycle"] = "open"
        self.request("PUT", path, tokens["teacher"], json=body)
        with self.Session() as db:
            enrollment = db.query(Enrollment).filter_by(section_id=section).first()
            enrollment.state = "withdrawn"
            db.commit()
        self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Retirado"}).status_code, 404)

    def test_task_transfer_normalization_privacy_and_idempotence(self):
        tokens, section = self.task_fixture()
        assessment = self.request("POST", "/assessments/", tokens["teacher"], json={"section_id": section, "name": "Proyecto entregable", "weight": 100, "due_date": "2099-01-01"}).json()
        body = {"section_id": section, "title": "Proyecto final", "instructions": "Desarrollar solución", "due_at": "2099-01-01T00:00:00Z", "max_score": 20, "assessment_id": assessment["assessment_id"]}
        task = self.request("POST", "/operations/assignments", tokens["teacher"], json=body)
        self.assertEqual(task.status_code, 200, task.text)
        path = f"/operations/assignments/{task.json()['assignment_id']}"
        duplicate = self.request("POST", "/operations/assignments", tokens["teacher"], json=body)
        self.assertEqual(duplicate.status_code, 409)
        submission = self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Proyecto"}).json()
        self.request("PATCH", f"/operations/submissions/{submission['submission_id']}/grade", tokens["teacher"], json={"score": 18, "feedback": "Muy bien"})
        transferred = self.request("POST", f"{path}/transfer-grades", tokens["teacher"], json={"reason": "Revisión de proyecto"})
        self.assertEqual(transferred.status_code, 200, transferred.text)
        self.assertEqual(transferred.json()["transferred"], 1)
        self.assertEqual(self.request("POST", f"{path}/transfer-grades", tokens["teacher"], json={"reason": "Revisión"}).json()["skipped"], 1)
        with self.Session() as db:
            note = db.query(Grade).filter_by(assessment_id=assessment["assessment_id"]).one()
            self.assertEqual((note.grade_value, note.status), (90, "draft"))
            note_id = note.grade_id
        self.assertEqual(self.request("GET", f"/grades/{note_id}", tokens["student"]).status_code, 404)
        self.assertEqual(self.request("POST", f"{path}/transfer-grades", tokens["student"], json={"reason": "Cambiar"}).status_code, 403)
        changed = self.request("PATCH", f"/operations/submissions/{submission['submission_id']}/grade", tokens["teacher"], json={"score": 16, "feedback": "Corrección"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.request("POST", f"{path}/transfer-grades", tokens["teacher"], json={"reason": "Corrección"}).status_code, 409)
        with self.Session() as db:
            self.assertEqual(db.get(Grade, note_id).grade_value, 90)
        agenda = self.request("GET", "/operations/agenda", tokens["student"])
        self.assertEqual(agenda.status_code, 200, agenda.text)
        self.assertTrue({"task", "assessment"}.issubset({e["kind"] for e in agenda.json()}))

    def test_task_section_assessment_period_and_event_scope(self):
        tokens, section = self.task_fixture()
        all_sections = self.request("GET", "/sections/", tokens["admin"]).json()
        other = next(s["section_id"] for s in all_sections if s["section_id"] != section)
        assessment = self.request("POST", "/assessments/", tokens["teacher"], json={"section_id": other, "name": "Otra evaluación", "weight": 100}).json()
        body = {"section_id": section, "title": "Actividad segura", "instructions": "Explicar razonamiento", "due_at": "2099-01-01T00:00:00Z", "assessment_id": assessment["assessment_id"]}
        self.assertEqual(self.request("POST", "/operations/assignments", tokens["teacher"], json=body).status_code, 422)
        body["assessment_id"] = None
        task = self.request("POST", "/operations/assignments", tokens["teacher"], json=body).json()
        path = f"/operations/assignments/{task['assignment_id']}"
        event_body = {"title": "Orientación de sección", "starts_at": "2099-01-01T09:00:00-04:00", "ends_at": "2099-01-01T10:00:00-04:00", "audience": "section", "section_id": section}
        event = self.request("POST", "/operations/calendar", tokens["teacher"], json=event_body)
        self.assertEqual(event.status_code, 200, event.text)
        self.assertTrue(event.json()["starts_at"].startswith("2099-01-01T13:"))
        event_path = f"/operations/calendar/{event.json()['calendar_event_id']}"
        self.assertEqual(self.request("PUT", event_path, tokens["student"], json=event_body).status_code, 403)
        event_body["audience"] = "all"
        self.assertEqual(self.request("PUT", event_path, tokens["teacher"], json=event_body).status_code, 403)
        with self.Session() as db:
            teacher = db.query(User).filter_by(username="demo.docente").one()
            teacher.teacher_id = None
            db.commit()
        self.assertEqual(self.request("GET", "/operations/assignments", tokens["teacher"]).json(), [])
        self.assertEqual(self.request("GET", f"{path}/submissions", tokens["teacher"]).status_code, 404)
        self.assertEqual(self.request("GET", "/operations/calendar", tokens["teacher"]).json(), [])
        with self.Session() as db:
            period = db.query(AcademicPeriod).first()
            period.status = "closed"
            db.commit()
        self.assertEqual(self.request("POST", f"{path}/submit", tokens["student"], json={"content": "Solución"}).status_code, 409)
        self.assertEqual(self.request("PUT", path, tokens["admin"], json=body).status_code, 409)

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
        alert_id = alert.json()["early_alert_id"]
        assigned = self.request(
            "PATCH",
            f"/operations/alerts/{alert_id}/assignment",
            token=admin_token,
            json={"assigned_to": None, "follow_up_date": "2026-10-01"},
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)
        intervention = self.request(
            "POST",
            f"/operations/alerts/{alert_id}/interventions",
            token=admin_token,
            json={"action_type": "meeting", "notes": "Reunión de seguimiento realizada"},
        )
        self.assertEqual(intervention.status_code, 200, intervention.text)
        intervention_list = self.request(
            "GET", f"/operations/alerts/{alert_id}/interventions", token=admin_token
        )
        self.assertEqual(intervention_list.status_code, 200, intervention_list.text)
        self.assertEqual(len(intervention_list.json()), 1)
        alert_resolved = self.request(
            "PATCH",
            f"/operations/alerts/{alert_id}/resolve",
            token=admin_token,
            json={"resolution_notes": "Objetivo de recuperación cumplido"},
        )
        self.assertEqual(alert_resolved.status_code, 200, alert_resolved.text)
        self.assertEqual(alert_resolved.json()["status"], "resolved")
        self.assertEqual(
            alert_resolved.json()["resolution_notes"], "Objetivo de recuperación cumplido"
        )
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
        application_path = f"/operations/admissions/{admission.json()['admission_application_id']}"
        self.assertEqual(self.request("POST", application_path + "/enroll", admin_token).status_code, 409)
        self.assertEqual(self.request("PATCH", application_path, admin_token, json={"status": "review"}).status_code, 200)
        self.assertEqual(self.request("PATCH", application_path, admin_token, json={"status": "accepted"}).status_code, 200)
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
        academic_analytics = self.request(
            "GET", "/operations/analytics/academic", token=admin_token
        )
        self.assertEqual(academic_analytics.status_code, 200, academic_analytics.text)
        self.assertIn("career_metrics", academic_analytics.json())
        self.assertIn("subject_metrics", academic_analytics.json())
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
        role_id = self.request("GET", "/roles/", token=admin_token).json()[0]["role_id"]
        role_permissions = self.request(
            "GET", f"/access/roles/{role_id}/permissions", token=admin_token
        )
        self.assertEqual(role_permissions.status_code, 200, role_permissions.text)
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
        self.assertIn("average_grade", overview.json()[0])
        self.assertIn("attendance_percentage", overview.json()[0])
        self.assertIn("balance", overview.json()[0])
        self.assertIn("schedule", overview.json()[0])
        self.assertIn("alerts", overview.json()[0])

    def test_period_closing_is_controlled_and_reversible(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        period = self.request(
            "POST",
            "/periods/",
            token=token,
            json={
                "name": "2027-PRUEBA",
                "start_date": "2027-01-10",
                "end_date": "2027-04-30",
                "status": "planning",
                "period_type": "quadrimester",
                "sequence": 1,
                "academic_year": "2027",
            },
        )
        self.assertEqual(period.status_code, 200, period.text)
        period_id = period.json()["period_id"]
        direct_close = self.request(
            "PATCH", f"/periods/{period_id}", token=token, json={"status": "closed"}
        )
        self.assertEqual(direct_close.status_code, 409, direct_close.text)
        closed = self.request("POST", f"/periods/{period_id}/close", token=token)
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertEqual(closed.json()["status"], "closed")
        reopened = self.request("POST", f"/periods/{period_id}/reopen", token=token)
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(reopened.json()["status"], "active")

    def test_configured_permissions_enforce_management_actions(self) -> None:
        with self.Session() as db:
            seed_demo(db)
            admin_role = db.query(Role).filter_by(name="admin").one()  # noqa: F405
            access = Permission(  # noqa: F405
                slug="access.manage", description="Gestionar acceso"
            )
            academic = Permission(  # noqa: F405
                slug="academic.manage", description="Gestionar academia"
            )
            operations = Permission(  # noqa: F405
                slug="operations.manage", description="Gestionar operaciones"
            )
            db.add_all([access, academic, operations])
            db.flush()
            db.add(  # noqa: F405
                RolePermission(role_id=admin_role.role_id, permission_id=access.permission_id)
            )
            db.commit()
        token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        denied = self.request(
            "POST",
            "/subjects/",
            token=token,
            json={"code": "PERM-01", "description": "Prueba de permiso"},
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        denied_event = self.request(
            "POST",
            "/operations/calendar",
            token=token,
            json={
                "title": "Evento restringido",
                "starts_at": "2026-11-01T09:00:00",
                "ends_at": "2026-11-01T10:00:00",
                "event_type": "activity",
                "audience": "all",
            },
        )
        self.assertEqual(denied_event.status_code, 403, denied_event.text)
        admin_role_id = self.request("GET", "/roles/", token=token).json()[0]["role_id"]
        granted = self.request(
            "PUT",
            f"/access/roles/{admin_role_id}/permissions",
            token=token,
            json={"permissions": ["access.manage", "academic.manage", "operations.manage"]},
        )
        self.assertEqual(granted.status_code, 200, granted.text)
        allowed = self.request(
            "POST",
            "/subjects/",
            token=token,
            json={"code": "PERM-01", "description": "Prueba de permiso"},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        allowed_event = self.request(
            "POST",
            "/operations/calendar",
            token=token,
            json={
                "title": "Evento autorizado",
                "starts_at": "2026-11-01T09:00:00",
                "ends_at": "2026-11-01T10:00:00",
                "event_type": "activity",
                "audience": "all",
            },
        )
        self.assertEqual(allowed_event.status_code, 200, allowed_event.text)

    def test_scheduling_rejects_room_and_teacher_conflicts(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        sections = self.request("GET", "/sections/", token=token).json()
        room = self.request(
            "POST",
            "/scheduling/classrooms",
            token=token,
            json={"name": "Aula Magna", "capacity": 60, "location": "Edificio A"},
        )
        self.assertEqual(room.status_code, 200, room.text)
        first = self.request(
            "POST",
            "/scheduling/meetings",
            token=token,
            json={
                "section_id": sections[0]["section_id"],
                "classroom_id": room.json()["classroom_id"],
                "day_of_week": "Lunes",
                "start_time": "08:00:00",
                "end_time": "09:30:00",
                "modality": "in_person",
            },
        )
        self.assertEqual(first.status_code, 200, first.text)
        conflict = self.request(
            "POST",
            "/scheduling/meetings",
            token=token,
            json={
                "section_id": sections[1]["section_id"],
                "classroom_id": room.json()["classroom_id"],
                "day_of_week": "Lunes",
                "start_time": "09:00:00",
                "end_time": "10:00:00",
                "modality": "in_person",
            },
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)
        listed = self.request(
            "GET", f"/scheduling/sections/{sections[0]['section_id']}/meetings", token=token
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()), 1)
        deleted = self.request(
            "DELETE", f"/scheduling/meetings/{first.json()['meeting_id']}", token=token
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)

    def test_finance_account_adjustments_plans_and_cash_closing(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        student_id = self.request("GET", "/students/", token=token).json()[0]["student_id"]
        account = self.request(
            "PUT",
            f"/finance/students/{student_id}/account",
            token=token,
            json={"cutoff_day": 10, "due_day": 20},
        )
        self.assertEqual(account.status_code, 200, account.text)
        charge = self.request(
            "POST",
            f"/finance/students/{student_id}/charges",
            token=token,
            json={"description": "Matrícula especial", "amount": 1200, "due_date": "2026-10-20"},
        )
        self.assertEqual(charge.status_code, 200, charge.text)
        adjustment = self.request(
            "POST",
            f"/finance/students/{student_id}/adjustments",
            token=token,
            json={"kind": "scholarship", "description": "Beca académica", "amount": 200},
        )
        self.assertEqual(adjustment.status_code, 200, adjustment.text)
        plan = self.request(
            "POST",
            f"/finance/students/{student_id}/payment-plans",
            token=token,
            json={"name": "Plan de dos cuotas", "installments": 2, "first_due_date": "2026-10-30"},
        )
        self.assertEqual(plan.status_code, 200, plan.text)
        self.assertEqual(plan.json()["installments"], 2)
        accounts = self.request("GET", "/finance/accounts", token=token)
        self.assertEqual(accounts.status_code, 200, accounts.text)
        closing = self.request("POST", "/finance/cash-closings/2026-09-21", token=token)
        self.assertEqual(closing.status_code, 200, closing.text)
        duplicate = self.request("POST", "/finance/cash-closings/2026-09-21", token=token)
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

    def test_curriculum_crud_preserves_university_course_metadata(self) -> None:
        with self.Session() as db:
            seed_demo(db)
        token = self.request(
            "POST", "/auth/login", json={"username": "demo.admin", "password": "NexoAdmin2026!"}
        ).json()["access_token"]
        career = self.request("GET", "/careers/", token=token).json()[0]
        subject = self.request(
            "POST",
            "/subjects/",
            token=token,
            json={"code": "CAP-401", "description": "Proyecto de grado"},
        ).json()
        created = self.request(
            "POST",
            "/curriculum/courses",
            token=token,
            json={
                "career_id": career["career_id"],
                "subject_id": subject["subject_id"],
                "term_number": 8,
                "credits": 6,
                "course_type": "capstone",
                "curriculum_version": "2027",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["course_type"], "capstone")
        self.assertEqual(created.json()["curriculum_version"], "2027")
        course_id = created.json()["curriculum_course_id"]
        updated = self.request(
            "PATCH",
            f"/curriculum/courses/{course_id}",
            token=token,
            json={"credits": 7, "curriculum_version": "2027.1"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["credits"], 7)
        listed = self.request(
            "GET", f"/curriculum/courses?career_id={career['career_id']}", token=token
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertTrue(any(item["curriculum_course_id"] == course_id for item in listed.json()))
        deleted = self.request("DELETE", f"/curriculum/courses/{course_id}", token=token)
        self.assertEqual(deleted.status_code, 200, deleted.text)


if __name__ == "__main__":
    unittest.main()
