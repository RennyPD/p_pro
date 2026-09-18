"""Agrega tutores de demostración a una institución existente sin borrar datos."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import Guardian, Permission, Role, RolePermission, Student, StudentGuardian, User
from app.security import hash_password

PASSWORD = "NexoTutor2026!"


def seed_guardians(db: Session, limit: int = 6) -> int:
    role = db.scalar(select(Role).where(Role.name == "guardian"))
    if role is None:
        role = Role(name="guardian", description="Consulta de estudiantes vinculados como tutor")
        db.add(role)
        db.flush()
    permission = db.scalar(select(Permission).where(Permission.slug == "records.own"))
    if permission and not db.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role.role_id,
            RolePermission.permission_id == permission.permission_id,
        )
    ):
        db.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    students = list(db.scalars(select(Student).order_by(Student.student_id).limit(limit)))
    created = 0
    for index, student in enumerate(students, start=1):
        username = f"tutor.{index:02d}"
        if db.scalar(select(User).where(User.username == username)):
            continue
        guardian = Guardian(
            first_name=f"Tutor {index}",
            last_name=student.last_name,
            email=f"tutor{index:02d}@horizonte.example",
            telephone=f"809-555-30{index:02d}",
            address=student.address,
        )
        db.add(guardian)
        db.flush()
        db.add(
            StudentGuardian(
                student_id=student.student_id,
                guardian_id=guardian.guardian_id,
                relationship="tutor",
                primary_contact=True,
                emergency_contact=True,
                authorized_pickup=True,
            )
        )
        db.add(
            User(
                username=username,
                email=guardian.email,
                password=hash_password(PASSWORD),
                role_id=role.role_id,
                guardian_id=guardian.guardian_id,
            )
        )
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    with SessionLocal() as session:
        print({"guardians_created": seed_guardians(session)})
