from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import ACADEMIC_SCOPE, get_current_user, has_permission, has_scope
from app.db.Session import get_db
from app.models.community_model import Guardian
from app.models.configuration_model import AcademicPeriod, InstitutionSettings
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.schemas.dashboard_schema import DashboardMetric, DashboardSummary
from app.services.academic_metrics import summarize_results
from app.services.dashboard_metrics import finance_metrics, student_extra_metrics, teacher_metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def display_name(db: Session, user: User) -> str:
    """First name of the linked person, so greetings never show a login handle."""
    person = (
        db.get(Student, user.student_id)
        if user.student_id
        else db.get(Teacher, user.teacher_id)
        if user.teacher_id
        else db.get(Guardian, user.guardian_id)
        if getattr(user, "guardian_id", None)
        else None
    )
    # Greeting only (not access control): admin accounts usually have no linked person.
    if person is None and user.role.name.casefold() == "admin":
        return "equipo de administración"
    return getattr(person, "first_name", None) or user.username


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    active_period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    alerts = []
    if active_period is None:
        alerts.append("No hay un período académico activo")
    if has_scope(user, *ACADEMIC_SCOPE):
        metrics = [
            DashboardMetric(
                key="students",
                label="Estudiantes",
                value=db.query(Student).filter(Student.active.is_(True)).count(),
                note="Expedientes activos",
                link="/students",
            ),
            DashboardMetric(
                key="teachers",
                label="Docentes",
                value=db.query(Teacher).filter(Teacher.active.is_(True)).count(),
                note="Equipo académico",
                link="/teachers",
            ),
            DashboardMetric(
                key="sections",
                label="Secciones",
                value=db.query(Section).count(),
                note="Oferta registrada",
                link="/sections",
            ),
            DashboardMetric(
                key="enrollments",
                label="Selecciones académicas",
                value=db.query(Enrollment).filter(Enrollment.period == active_period.name).count()
                if active_period
                else db.query(Enrollment).count(),
                note=active_period.name if active_period else "Todos los períodos",
            ),
        ]
        if has_permission(user, "finance.view"):
            metrics += finance_metrics(db)
        settings = db.get(InstitutionSettings, 1)
        if settings is None:
            alerts.append("Completa la configuración institucional")
        return DashboardSummary(
            display_name=display_name(db, user),
            role="admin",
            metrics=metrics,
            active_period=active_period.name if active_period else None,
            alerts=alerts,
        )
    if user.teacher_id is not None:
        metrics = teacher_metrics(db, user.teacher_id)
        return DashboardSummary(
            display_name=display_name(db, user),
            role="teacher",
            metrics=metrics,
            active_period=active_period.name if active_period else None,
            alerts=alerts,
        )
    enrollment_query = db.query(Enrollment).filter(Enrollment.student_id == user.student_id)
    if active_period:
        enrollment_query = enrollment_query.filter(Enrollment.period == active_period.name)
    enrollments = enrollment_query.filter(
        Enrollment.state.in_(("enrolled", "completed", "failed"))
    ).all()
    summary = summarize_results(db, enrollments)
    period_name = active_period.name if active_period else "Todos los períodos"
    final = summary["average_grade"] is not None
    average = summary["average_grade"] if final else summary["provisional_average_grade"]
    attendance = summary["attendance_percentage"]
    metrics = [
        DashboardMetric(
            key="average",
            label="Promedio" if final else "Promedio provisional",
            value=average,
            note=f"{len(enrollments)} asignaturas · {period_name}",
            tone="warning" if average is not None and average < 70 else "default",
            link="/my-grades",
        ),
        DashboardMetric(
            key="attendance",
            label="Asistencia",
            value=attendance,
            note=f"{summary['attendance_count']} clases registradas",
            tone="warning" if attendance is not None and attendance < 80 else "default",
            link="/my-attendance",
        ),
        *student_extra_metrics(db, user.student_id),
    ]
    return DashboardSummary(
        display_name=display_name(db, user),
        role="student",
        metrics=metrics,
        active_period=active_period.name if active_period else None,
        alerts=alerts,
    )
