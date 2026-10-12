from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, is_admin
from app.db.Session import get_db
from app.models.configuration_model import AcademicPeriod, InstitutionSettings
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.schemas.dashboard_schema import DashboardMetric, DashboardSummary
from app.services.academic_grading import academic_result

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    active_period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    alerts = []
    if active_period is None:
        alerts.append("No hay un período académico activo")
    if is_admin(user):
        metrics = [
            DashboardMetric(
                key="students",
                label="Estudiantes",
                value=db.query(Student).filter(Student.active.is_(True)).count(),
                note="Expedientes activos",
            ),
            DashboardMetric(
                key="teachers",
                label="Docentes",
                value=db.query(Teacher).filter(Teacher.active.is_(True)).count(),
                note="Equipo académico",
            ),
            DashboardMetric(
                key="sections",
                label="Secciones",
                value=db.query(Section).count(),
                note="Oferta registrada",
            ),
            DashboardMetric(
                key="enrollments",
                label="Inscripciones",
                value=db.query(Enrollment).filter(Enrollment.period == active_period.name).count()
                if active_period
                else db.query(Enrollment).count(),
                note="En el período activo",
            ),
        ]
        settings = db.get(InstitutionSettings, 1)
        if settings is None:
            alerts.append("Completa la configuración institucional")
        return DashboardSummary(
            role="admin",
            metrics=metrics,
            active_period=active_period.name if active_period else None,
            alerts=alerts,
        )
    if user.teacher_id is not None:
        sections = db.query(Section).filter(Section.teacher_id == user.teacher_id)
        student_count = (
            db.query(func.count(func.distinct(Enrollment.student_id)))
            .join(Section, Enrollment.section_id == Section.section_id)
            .filter(Section.teacher_id == user.teacher_id)
            .scalar()
        ) or 0
        metrics = [
            DashboardMetric(
                key="sections",
                label="Mis secciones",
                value=sections.count(),
                note="Secciones asignadas",
            ),
            DashboardMetric(
                key="students",
                label="Mis estudiantes",
                value=student_count,
                note="Estudiantes distintos",
            ),
            DashboardMetric(
                key="grades",
                label="Notas registradas",
                value=db.query(Grade)
                .join(Enrollment)
                .join(Section)
                .filter(Section.teacher_id == user.teacher_id)
                .count(),
                note="Evaluaciones acumuladas",
            ),
        ]
        return DashboardSummary(
            role="teacher",
            metrics=metrics,
            active_period=active_period.name if active_period else None,
            alerts=alerts,
        )
    enrollments = db.query(Enrollment).filter(Enrollment.student_id == user.student_id).all()
    grades = [
        result.value
        for item in enrollments
        if (result := academic_result(db, item)).value is not None
    ]
    attendances = [record for item in enrollments for record in item.attendances]
    metrics = [
        DashboardMetric(
            key="courses",
            label="Asignaturas",
            value=len(enrollments),
            note="Inscripciones acumuladas",
        ),
        DashboardMetric(
            key="average",
            label="Promedio",
            value=round(sum(grades) / len(grades), 1) if grades else 0,
            note="Promedio general",
        ),
        DashboardMetric(
            key="attendance",
            label="Asistencia",
            value=round(sum(item.present for item in attendances) * 100 / len(attendances), 1)
            if attendances
            else 0,
            note="Porcentaje general",
        ),
    ]
    return DashboardSummary(
        role="student",
        metrics=metrics,
        active_period=active_period.name if active_period else None,
        alerts=alerts,
    )
