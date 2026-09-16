import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models import *  # noqa: F403 - registers all tables
from app.repositories.role_repository import create_role, delete_role, get_role_by_id, update_role
from app.repositories.subject_repository import create_subject, get_subject_by_id, update_subject
from app.repositories.teacher_repository import create_teacher, get_teacher_by_id, update_teacher
from app.schemas.role_schema import RoleCreate, RoleUpdate
from app.schemas.subject_schema import SubjectCreate, SubjectUpdate
from app.schemas.teacher_schema import TeacherCreate, TeacherUpdate


class CrudTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_role_crud_and_partial_update(self) -> None:
        role = create_role(self.session, RoleCreate(name="admin", description="Admin"))
        updated = update_role(self.session, role.role_id, RoleUpdate(description="Administrator"))
        self.assertEqual(updated.name, "admin")
        self.assertEqual(updated.description, "Administrator")
        self.assertTrue(delete_role(self.session, role.role_id))
        self.assertIsNone(get_role_by_id(self.session, role.role_id))

    def test_subject_create_read_and_partial_update(self) -> None:
        subject = create_subject(
            self.session,
            SubjectCreate(code="MAT-101", description="Mathematics"),
        )
        updated = update_subject(
            self.session,
            subject.subject_id,
            SubjectUpdate(description="Basic mathematics"),
        )
        self.assertEqual(updated.code, "MAT-101")
        self.assertEqual(
            get_subject_by_id(self.session, subject.subject_id).description, "Basic mathematics"
        )

    def test_teacher_create_read_and_partial_update(self) -> None:
        teacher = create_teacher(
            self.session,
            TeacherCreate(
                first_name="Ada",
                last_name="Lovelace",
                specialty="Mathematics",
                email="ada@example.com",
                telephone="555-0100",
                address="Santo Domingo",
            ),
        )
        updated = update_teacher(
            self.session,
            teacher.teacher_id,
            TeacherUpdate(specialty="Computer science"),
        )
        self.assertEqual(updated.first_name, "Ada")
        self.assertEqual(
            get_teacher_by_id(self.session, teacher.teacher_id).specialty, "Computer science"
        )


if __name__ == "__main__":
    unittest.main()
