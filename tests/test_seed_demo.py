import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models import (
    AcademicPeriod,
    Attendance,
    Career,
    Enrollment,
    Grade,
    Role,
    Section,
    Student,
    Subject,
    Teacher,
    User,
)
from scripts.seed_demo import DEMO_EMAILS, seed_demo


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_seed_is_idempotent_and_builds_complete_scenario(self):
        with Session(self.engine) as db:
            seed_demo(db)
            seed_demo(db)
            expected = {
                AcademicPeriod: 1,
                Role: 3,
                Career: 1,
                Subject: 2,
                Teacher: 1,
                Student: 1,
                Section: 2,
                Enrollment: 2,
                Grade: 1,
                Attendance: 1,
                User: 3,
            }
            for model, count in expected.items():
                self.assertEqual(db.scalar(select(func.count()).select_from(model)), count)
            section = db.scalar(select(Section).where(Section.code == "PROG-101-A"))
            self.assertEqual(section.days_of_week, "Lunes, Miércoles")
            student = db.scalar(select(Student).where(Student.enrollment_number == "DEMO-2026-001"))
            self.assertEqual(student.email, DEMO_EMAILS["demo.estudiante"])

    def test_seed_repairs_legacy_demo_local_emails(self):
        with Session(self.engine) as db:
            seed_demo(db)
            student = db.scalar(select(Student).where(Student.enrollment_number == "DEMO-2026-001"))
            teacher = db.scalar(select(Teacher).where(Teacher.teacher_id == 1))
            users = list(db.scalars(select(User)))
            student.email = "daniel.demo@nexo.local"
            teacher.email = "elena.demo@nexo.local"
            for user in users:
                user.email = f"{user.username}@nexo.local"
            db.commit()

            seed_demo(db)

            self.assertEqual(student.email, DEMO_EMAILS["demo.estudiante"])
            self.assertEqual(teacher.email, DEMO_EMAILS["demo.docente"])
            self.assertEqual(
                {user.username: user.email for user in users},
                DEMO_EMAILS,
            )


if __name__ == "__main__":
    unittest.main()
