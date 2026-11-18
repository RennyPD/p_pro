import base64
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import (
    ensure_section_access,
    ensure_student_academic_access,
    get_current_user,
    is_admin,
    require_permissions,
    require_roles,
)
from app.db.Session import get_db
from app.models.attendance_model import Attendance
from app.models.career_model import Career
from app.models.community_model import StudentGuardian
from app.models.configuration_model import AcademicPeriod
from app.models.enrollment_model import Enrollment
from app.models.finance_model import StudentAccount
from app.models.operations_model import (
    AdmissionApplication,
    AlertIntervention,
    ApprovalRequest,
    Assignment,
    CalendarEvent,
    EarlyAlert,
    LessonPlan,
    StudentDocument,
    Submission,
)
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.routers.assignment_router import router as assignment_routes
from app.routers.assignment_router import scope, utc
from app.schemas.operations_schema import (
    AdmissionCreate,
    AdmissionOut,
    AdmissionUpdate,
    AlertAssignment,
    AlertCreate,
    AlertInterventionCreate,
    AlertInterventionOut,
    AlertOut,
    AlertResolve,
    ApprovalCreate,
    ApprovalOut,
    ApprovalResolve,
    CalendarEventCreate,
    CalendarEventOut,
    LessonPlanCreate,
    LessonPlanOut,
    LessonPlanResolve,
    StudentDocumentCreate,
    StudentDocumentOut,
)
from app.schemas.student_schema import StudentCreate
from app.services.academic_grading import academic_result
from app.services.academic_metrics import summarize_results
from app.services.effective_schedule import effective_blocks
from app.services.finance_workflow import cents, money
from app.services.finance_workflow import summary as finance_summary
from app.services.governance_workflow import history as governance_history
from app.services.governance_workflow import lock_governance, record
from app.services.student_service import create_student_service

router = APIRouter(prefix="/operations", tags=["institutional operations"])
router.include_router(assignment_routes)
operations_manager = require_permissions("operations.manage", fallback_roles=("admin", "teacher"))
operations_admin = require_permissions(
    "operations.manage", fallback_roles=("admin",), institutional=True
)


def student_scope_ids(db: Session, user: User) -> list[int] | None:
    if is_admin(user):
        return None
    if user.student_id:
        return [user.student_id]
    if user.teacher_id:
        return [
            row[0]
            for row in db.query(Enrollment.student_id)
            .join(Section)
            .filter(Section.teacher_id == user.teacher_id)
            .distinct()
        ]
    if user.guardian_id:
        return [
            row[0]
            for row in db.query(StudentGuardian.student_id).filter(
                StudentGuardian.guardian_id == user.guardian_id
            )
        ]
    return []


@router.get("/calendar", response_model=list[CalendarEventOut])
def calendar(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(CalendarEvent)
    role = user.role.name.casefold()
    if not is_admin(user):
        query = query.filter(
            ((CalendarEvent.audience.in_(["all", role])) & CalendarEvent.section_id.is_(None))
            | (
                (CalendarEvent.audience == "section")
                & CalendarEvent.section_id.in_(scope(db, user))
            )
        )
    return query.order_by(CalendarEvent.starts_at).all()


@router.post("/calendar", response_model=CalendarEventOut)
def create_event(
    data: CalendarEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    if not is_admin(user):
        if data.audience != "section":
            raise HTTPException(status_code=403, detail="Teachers can only create section events")
        ensure_section_access(db, user, data.section_id or 0)
    if data.section_id:
        ensure_section_access(db, user, data.section_id)
    values = data.model_dump()
    values.update(starts_at=utc(data.starts_at), ends_at=utc(data.ends_at))
    if data.audience != "section":
        values["section_id"] = None
    item = CalendarEvent(**values, created_by=user.user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/calendar/{event_id}", response_model=CalendarEventOut)
def edit_event(
    event_id: int,
    data: CalendarEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    item = db.get(CalendarEvent, event_id)
    if not item:
        raise HTTPException(404, "Evento no disponible")
    if not is_admin(user):
        if item.audience != "section" or data.audience != "section":
            raise HTTPException(403, "Solo puedes editar eventos de tus secciones")
        ensure_section_access(db, user, item.section_id)
        ensure_section_access(db, user, data.section_id or 0)
    elif data.section_id:
        ensure_section_access(db, user, data.section_id)
    for key, value in data.model_dump().items():
        setattr(item, key, utc(value) if key in {"starts_at", "ends_at"} else value)
    if data.audience != "section":
        item.section_id = None
    db.commit()
    db.refresh(item)
    return item


@router.get("/lesson-plans", response_model=list[LessonPlanOut])
def lesson_plans(
    section_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    query = db.query(LessonPlan)
    if not is_admin(user):
        query = query.filter(LessonPlan.teacher_id == user.teacher_id)
    if section_id:
        query = query.filter(LessonPlan.section_id == section_id)
    return query.order_by(LessonPlan.scheduled_date.desc()).all()


@router.post("/lesson-plans", response_model=LessonPlanOut)
def create_lesson_plan(
    data: LessonPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    section = ensure_section_access(db, user, data.section_id)
    if section.status in {"closed", "cancelled"}:
        raise HTTPException(409, "La sección está cerrada o cancelada")
    item = LessonPlan(**data.model_dump(), teacher_id=section.teacher_id)
    db.add(item)
    db.flush()
    record(
        db,
        user,
        "lesson_plan.created",
        f"lesson-plan:{item.lesson_plan_id}",
        f"Sección {section.code}",
    )
    db.commit()
    db.refresh(item)
    return item


def writable_lesson_plan(db, user, plan_id):
    item = db.get(LessonPlan, plan_id)
    if item is None:
        raise HTTPException(404, "No se encontró el plan de clase")
    section = ensure_section_access(db, user, item.section_id)
    if not is_admin(user) and item.teacher_id != user.teacher_id:
        raise HTTPException(403, "El plan pertenece a otro docente")
    if section.status in {"closed", "cancelled"} or item.status != "planned":
        raise HTTPException(409, "Solo se puede cambiar un plan programado en una sección abierta")
    return item


@router.put("/lesson-plans/{plan_id}", response_model=LessonPlanOut)
def edit_lesson_plan(
    plan_id: int,
    data: LessonPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    item = writable_lesson_plan(db, user, plan_id)
    if item.section_id != data.section_id or data.status != "planned":
        raise HTTPException(409, "Conserva la sección y usa la acción de cierre del plan")
    for key, value in data.model_dump(exclude={"section_id", "status"}).items():
        setattr(item, key, value)
    record(db, user, "lesson_plan.updated", f"lesson-plan:{plan_id}", "Contenido revisado")
    db.commit()
    return item


@router.patch("/lesson-plans/{plan_id}/status", response_model=LessonPlanOut)
def finish_lesson_plan(
    plan_id: int,
    data: LessonPlanResolve,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    item = writable_lesson_plan(db, user, plan_id)
    item.status = data.status
    record(db, user, "lesson_plan.status", f"lesson-plan:{plan_id}", f"planned → {data.status}")
    db.commit()
    return item


@router.get("/alerts", response_model=list[AlertOut])
def alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(EarlyAlert)
    ids = student_scope_ids(db, user)
    if ids is not None:
        query = query.filter(EarlyAlert.student_id.in_(ids))
    result = []
    for item in query.order_by(EarlyAlert.created_at.desc()):
        value = AlertOut.model_validate(item)
        student = db.get(Student, item.student_id)
        value.student_name, value.enrollment_number = student.full_name, student.enrollment_number
        result.append(value)
    return result


@router.get("/alert-assignees")
def alert_assignees(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(operations_manager)
):
    ensure_student_academic_access(db, user, student_id)
    result = []
    for candidate in (
        db.query(User)
        .join(User.role)
        .filter(User.role.has(name="admin") | User.role.has(name="teacher"))
    ):
        try:
            ensure_student_academic_access(db, candidate, student_id)
        except HTTPException:
            continue
        teacher = db.get(Teacher, candidate.teacher_id) if candidate.teacher_id else None
        if teacher and not teacher.active:
            continue
        result.append(
            {
                "user_id": candidate.user_id,
                "name": f"{teacher.first_name} {teacher.last_name}"
                if teacher
                else candidate.username,
            }
        )
    return result


@router.post("/alerts", response_model=AlertOut)
def create_alert(
    data: AlertCreate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    ensure_student_academic_access(db, user, data.student_id)
    if db.get(Student, data.student_id) is None:
        raise HTTPException(404, "Selecciona un estudiante existente")
    item = EarlyAlert(**data.model_dump(), created_by=user.user_id)
    db.add(item)
    db.flush()
    record(db, user, "alert.created", f"alert:{item.early_alert_id}", "Alta manual de caso")
    db.commit()
    db.refresh(item)
    return item


@router.patch("/alerts/{alert_id}/assignment", response_model=AlertOut)
def assign_alert(
    alert_id: int,
    data: AlertAssignment,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    item = db.get(EarlyAlert, alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, item.student_id)
    if item.status != "open":
        raise HTTPException(409, "Solo se asignan casos abiertos")
    if data.assigned_to is not None:
        assignee = db.get(User, data.assigned_to)
        if assignee is None or assignee.role.name.casefold() not in {"admin", "teacher"}:
            raise HTTPException(422, "El responsable debe ser un administrador o docente")
        if assignee.teacher_id:
            teacher = db.get(Teacher, assignee.teacher_id)
            if not teacher or not teacher.active:
                raise HTTPException(422, "El docente responsable debe estar activo")
        ensure_student_academic_access(db, assignee, item.student_id)
    item.assigned_to = data.assigned_to
    item.follow_up_date = data.follow_up_date
    record(
        db,
        user,
        "alert.assigned",
        f"alert:{alert_id}",
        f"Responsable {data.assigned_to}; seguimiento {data.follow_up_date}",
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/alerts/{alert_id}/interventions", response_model=list[AlertInterventionOut])
def alert_interventions(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(EarlyAlert, alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, item.student_id)
    items = (
        db.query(AlertIntervention)
        .filter_by(early_alert_id=alert_id)
        .order_by(AlertIntervention.created_at.desc())
        .all()
    )
    result = []
    for item in items:
        value = AlertInterventionOut.model_validate(item)
        actor = db.get(User, item.performed_by)
        value.performer_name = actor.username if actor else "Registro histórico"
        result.append(value)
    return result


@router.post("/alerts/{alert_id}/interventions", response_model=AlertInterventionOut)
def add_alert_intervention(
    alert_id: int,
    data: AlertInterventionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    alert = db.get(EarlyAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, alert.student_id)
    if alert.status != "open" or len(data.notes.strip()) < 2:
        raise HTTPException(409, "Reabre el caso e indica una actuación completa")
    item = AlertIntervention(
        early_alert_id=alert_id,
        performed_by=user.user_id,
        **data.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/alerts/generate", dependencies=[Depends(operations_admin)])
def generate_alerts(db: Session = Depends(get_db), user: User = Depends(operations_admin)):
    lock_governance(db)
    created = 0
    for student in db.query(Student).filter(Student.active.is_(True)).all():
        results = [
            academic_result(db, e)
            for e in db.query(Enrollment).filter_by(student_id=student.student_id)
        ]
        attendance_rows = (
            db.query(Attendance.present)
            .join(Enrollment)
            .filter(
                Enrollment.student_id == student.student_id,
                Enrollment.state.in_(("enrolled", "completed", "failed")),
            )
            .all()
        )
        account = db.query(StudentAccount).filter_by(student_id=student.student_id).first()
        checks = []
        if any(r.status == "failed" for r in results):
            checks.append(
                (
                    "academic",
                    "high",
                    "Hay resultados finales reprobados según el criterio de cada selección",
                )
            )
        if (
            attendance_rows
            and sum(bool(row[0]) for row in attendance_rows) / len(attendance_rows) < 0.8
        ):
            checks.append(("attendance", "high", "Asistencia acumulada inferior al 80%"))
        if account and finance_summary(account).balance > 0:
            checks.append(("financial", "medium", "Balance financiero pendiente"))
        for category, severity, reason in checks:
            exists = (
                db.query(EarlyAlert)
                .filter_by(student_id=student.student_id, category=category, status="open")
                .first()
            )
            if not exists:
                db.add(
                    EarlyAlert(
                        student_id=student.student_id,
                        category=category,
                        severity=severity,
                        reason=reason,
                        created_by=user.user_id,
                    )
                )
                created += 1
    record(
        db,
        user,
        "alerts.generated",
        "institutional-alerts",
        f"Revisión automática global: {created} casos nuevos; no se cierran casos existentes automáticamente",
    )
    db.commit()
    return {"created": created}


@router.patch(
    "/alerts/{alert_id}/resolve",
    response_model=AlertOut,
)
def resolve_alert(
    alert_id: int,
    data: AlertResolve | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    item = db.get(EarlyAlert, alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, item.student_id)
    if item.status != "open" or data is None or len(data.resolution_notes.strip()) < 3:
        raise HTTPException(409, "El caso debe estar abierto e incluir un motivo de resolución")
    record(db, user, "alert.resolved", f"alert:{alert_id}", data.resolution_notes)
    db.add(
        AlertIntervention(
            early_alert_id=alert_id,
            performed_by=user.user_id,
            action_type="note",
            notes="Resolución: " + data.resolution_notes,
        )
    )
    item.status = "resolved"
    item.resolution_notes = data.resolution_notes if data else ""
    item.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/alerts/{alert_id}/reopen", response_model=AlertOut)
def reopen_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(operations_manager),
):
    lock_governance(db)
    item = db.get(EarlyAlert, alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, item.student_id)
    if item.status != "resolved":
        raise HTTPException(409, "El caso ya está abierto")
    record(
        db,
        user,
        "alert.reopened",
        f"alert:{alert_id}",
        "Reapertura; resolución anterior: " + item.resolution_notes,
    )
    db.add(
        AlertIntervention(
            early_alert_id=alert_id,
            performed_by=user.user_id,
            action_type="note",
            notes="Reapertura. Resolución anterior: " + item.resolution_notes,
        )
    )
    item.status = "open"
    item.resolved_at = None
    item.resolution_notes = ""
    db.commit()
    db.refresh(item)
    return item


@router.get("/guardian/overview")
def guardian_overview(
    db: Session = Depends(get_db), user: User = Depends(require_roles("guardian"))
):
    ids = student_scope_ids(db, user) or []
    active_period = db.query(AcademicPeriod).filter_by(active=True).first()
    result = []
    for student in db.query(Student).filter(Student.student_id.in_(ids)).all():
        enrollments = db.query(Enrollment).filter_by(student_id=student.student_id).all()
        summary = summarize_results(
            db,
            [item for item in enrollments if active_period and item.period == active_period.name],
        )
        account = db.query(StudentAccount).filter_by(student_id=student.student_id).first()
        balance = finance_summary(account).balance if account else 0
        alerts = (
            db.query(EarlyAlert)
            .filter_by(student_id=student.student_id, status="open")
            .order_by(EarlyAlert.created_at.desc())
            .all()
        )
        result.append(
            {
                "student_id": student.student_id,
                "student_name": f"{student.first_name} {student.last_name}",
                "enrollment_number": student.enrollment_number,
                "career_name": student.career.name,
                "active": student.active,
                **summary,
                "metrics_period": active_period.name if active_period else None,
                "balance": round(float(balance), 2),
                "schedule": [
                    {
                        "section_id": item.section_id,
                        "section_code": item.section.code,
                        "subject_name": item.section.subject.description,
                        "days_of_week": item.section.days_of_week,
                        "start_time": item.section.start_time.isoformat(),
                        "end_time": item.section.end_time.isoformat(),
                        "room": item.section.room,
                        "modality": item.section.modality,
                        "blocks": effective_blocks(item.section),
                    }
                    for item in enrollments
                    if active_period
                    and item.period == active_period.name
                    and item.state == "enrolled"
                    and item.section.status in {"published", "active"}
                ],
                "alerts": [
                    {
                        "early_alert_id": alert.early_alert_id,
                        "category": alert.category,
                        "severity": alert.severity,
                        "reason": alert.reason,
                        "follow_up_date": alert.follow_up_date,
                    }
                    for alert in alerts
                ],
            }
        )
    return result


@router.get(
    "/admissions", response_model=list[AdmissionOut], dependencies=[Depends(operations_admin)]
)
def admissions(db: Session = Depends(get_db)):
    items = db.query(AdmissionApplication).order_by(AdmissionApplication.created_at.desc()).all()
    return [admission_out(db, item) for item in items]


def admission_out(db, item):
    value = AdmissionOut.model_validate(item)
    career = db.get(Career, item.career_id)
    value.career_name = career.name if career else "Carrera no disponible"
    return value


@router.get("/admissions/{application_id}/history", dependencies=[Depends(operations_admin)])
def admission_history(application_id: int, db: Session = Depends(get_db)):
    if not db.get(AdmissionApplication, application_id):
        raise HTTPException(404, "Solicitud no encontrada")
    return governance_history(db, f"admission:{application_id}")


@router.post("/admissions", response_model=AdmissionOut, dependencies=[Depends(operations_admin)])
def create_admission(
    data: AdmissionCreate, db: Session = Depends(get_db), user: User = Depends(operations_admin)
):
    lock_governance(db)
    if not db.get(Career, data.career_id):
        raise HTTPException(404, "Carrera no encontrada")
    item = AdmissionApplication(**data.model_dump())
    db.add(item)
    db.flush()
    record(
        db,
        user,
        "admission.created",
        f"admission:{item.admission_application_id}",
        f"Solicitud recibida: {item.first_name} {item.last_name}",
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/admissions/{application_id}",
    response_model=AdmissionOut,
    dependencies=[Depends(operations_admin)],
)
def update_admission(
    application_id: int,
    data: AdmissionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_admin),
):
    lock_governance(db)
    item = db.get(AdmissionApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found")
    allowed = {
        "submitted": {"review", "rejected"},
        "review": {"accepted", "rejected"},
        "accepted": {"review", "rejected"},
        "rejected": {"review"},
        "enrolled": set(),
    }
    if data.expected_status is not None and item.status != data.expected_status:
        raise HTTPException(409, "La solicitud cambió; recarga su estado antes de continuar")
    if item.status == "enrolled" or (
        data.status != item.status and data.status not in allowed.get(item.status, set())
    ):
        raise HTTPException(
            409,
            "Transición de admisión no permitida; la matrícula se crea desde una solicitud aceptada",
        )
    record(
        db,
        user,
        "admission.updated",
        f"admission:{application_id}",
        f"{data.reason}; {item.status} → {data.status}",
    )
    for key, value in data.model_dump(
        exclude_unset=True, exclude_none=True, exclude={"reason", "expected_status"}
    ).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/admissions/{application_id}/enroll",
    dependencies=[Depends(operations_admin)],
)
def enroll_admission(
    application_id: int, db: Session = Depends(get_db), user: User = Depends(operations_admin)
):
    lock_governance(db)
    item = db.get(AdmissionApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if item.status == "enrolled":
        if item.student_id:
            student = db.get(Student, item.student_id)
            return {
                "student_id": student.student_id,
                "enrollment_number": student.enrollment_number,
            }
        raise HTTPException(
            409, "Solicitud histórica matriculada sin vínculo; requiere revisión manual"
        )
    if item.status != "accepted":
        raise HTTPException(409, "Primero acepta la solicitud después de revisarla")
    student = create_student_service(
        db,
        StudentCreate(
            first_name=item.first_name,
            last_name=item.last_name,
            email=item.email,
            telephone=item.telephone,
            address="Pendiente de completar",
            career_id=item.career_id,
        ),
        commit=False,
    )
    item.status = "enrolled"
    item.student_id = student.student_id
    record(
        db,
        user,
        "admission.enrolled",
        f"admission:{application_id}",
        f"Creado estudiante {student.enrollment_number}",
    )
    db.commit()
    return {"student_id": student.student_id, "enrollment_number": student.enrollment_number}


@router.get(
    "/approvals", response_model=list[ApprovalOut], dependencies=[Depends(operations_admin)]
)
def approvals(db: Session = Depends(get_db)):
    return db.query(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()).all()


@router.get("/approvals/mine", response_model=list[ApprovalOut])
def my_approvals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(ApprovalRequest)
        .filter_by(requested_by=user.user_id)
        .order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.approval_request_id.desc())
        .all()
    )


def ensure_approval_resource(db, user, data):
    if data.resource_type == "student":
        resource = db.get(Student, data.resource_id)
        ids = student_scope_ids(db, user)
        allowed = resource is not None and (ids is None or resource.student_id in ids)
    elif data.resource_type == "section":
        allowed = (
            db.query(Section)
            .filter(Section.section_id == data.resource_id, Section.section_id.in_(scope(db, user)))
            .first()
            is not None
        )
    elif data.resource_type == "submission":
        resource = db.get(Submission, data.resource_id)
        task = db.get(Assignment, resource.assignment_id) if resource else None
        if task is None:
            allowed = False
        elif is_admin(user):
            allowed = True
        elif user.teacher_id:
            allowed = db.get(Section, task.section_id).teacher_id == user.teacher_id
        else:
            allowed = task.published and resource.student_id in (student_scope_ids(db, user) or [])
    else:
        raise HTTPException(422, "Solicita revisión de una sección, un expediente o una entrega")
    if not allowed:
        raise HTTPException(404, "El recurso de esta solicitud no está disponible para tu cuenta")


@router.post("/approvals", response_model=ApprovalOut)
def request_approval(
    data: ApprovalCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    lock_governance(db)
    ensure_approval_resource(db, user, data)
    item = ApprovalRequest(**data.model_dump(), requested_by=user.user_id)
    db.add(item)
    db.flush()
    record(
        db,
        user,
        "approval.requested",
        f"approval:{item.approval_request_id}",
        "Solicitud registrada",
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/approvals/{request_id}", response_model=ApprovalOut)
def resolve_approval(
    request_id: int,
    data: ApprovalResolve,
    db: Session = Depends(get_db),
    user: User = Depends(operations_admin),
):
    lock_governance(db)
    item = db.get(ApprovalRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if item.status != "pending":
        raise HTTPException(409, "La solicitud ya fue resuelta. Consulta la decisión registrada")
    if len(data.resolution_notes.strip()) < 2:
        raise HTTPException(422, "Explica el motivo de la decisión")
    item.status = data.status
    item.resolution_notes = data.resolution_notes
    item.resolved_by = user.user_id
    item.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    record(db, user, "approval.resolved", f"approval:{request_id}", f"pending → {data.status}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/students/{student_id}/documents", response_model=list[StudentDocumentOut])
def documents(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_academic_access(db, user, student_id)
    return (
        db.query(StudentDocument)
        .filter_by(student_id=student_id)
        .order_by(StudentDocument.uploaded_at.desc(), StudentDocument.student_document_id.desc())
        .all()
    )


@router.post("/students/{student_id}/documents", response_model=StudentDocumentOut)
def upload_document(
    student_id: int,
    data: StudentDocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(operations_admin),
):
    if db.get(Student, student_id) is None:
        raise HTTPException(404, "El expediente del estudiante ya no está disponible")
    try:
        content = base64.b64decode(data.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(
            422, "El contenido no se pudo leer. Selecciona otra vez el archivo"
        ) from exc
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "El documento supera 5 MB")
    signatures = {
        "application/pdf": (b"%PDF-", (".pdf",)),
        "image/png": (b"\x89PNG\r\n\x1a\n", (".png",)),
        "image/jpeg": (b"\xff\xd8\xff", (".jpg", ".jpeg")),
    }
    signature, extensions = signatures[data.mime_type]
    filename = data.filename.replace("\\", "/").split("/")[-1].strip()
    if (
        not filename.casefold().endswith(extensions)
        or not content.startswith(signature)
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise HTTPException(
            422, "Selecciona un PDF, PNG o JPEG cuya extensión coincida con su contenido"
        )
    item = StudentDocument(
        student_id=student_id,
        document_type=data.document_type,
        filename=filename,
        mime_type=data.mime_type,
        content=content,
        expires_on=data.expires_on,
        uploaded_by=user.user_id,
    )
    db.add(item)
    db.flush()
    record(
        db,
        user,
        "document.uploaded",
        f"document:{item.student_document_id}",
        f"Expediente {student_id}",
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    item = db.get(StudentDocument, document_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Document not found")
    ensure_student_academic_access(db, user, item.student_id)
    return Response(
        item.content,
        media_type=item.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(item.filename, safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/analytics/summary",
    dependencies=[Depends(require_permissions("reports.view", fallback_roles=("admin",)))],
)
def analytics(period: str | None = None, db: Session = Depends(get_db)):
    students = db.query(Student).count()
    active = db.query(Student).filter(Student.active.is_(True)).count()
    query = db.query(Enrollment)
    if period:
        if db.query(AcademicPeriod).filter_by(name=period).first() is None:
            raise HTTPException(404, "Período no encontrado")
        query = query.filter(Enrollment.period == period)
    enrollments = query.all()
    receivables = sum(
        cents(finance_summary(account).balance) for account in db.query(StudentAccount).all()
    )
    return {
        "students": students,
        "active_students": active,
        "enrollments": len(enrollments),
        "metrics_period": period,
        **summarize_results(db, enrollments),
        "open_alerts": db.query(EarlyAlert).filter_by(status="open").count(),
        "receivables": money(receivables),
        "admission_pipeline": db.query(AdmissionApplication)
        .filter(AdmissionApplication.status.notin_(["rejected", "enrolled"]))
        .count(),
    }


def percentage(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) * 100 / float(denominator), 2) if denominator else 0


@router.get(
    "/analytics/academic",
    dependencies=[Depends(require_permissions("reports.view", fallback_roles=("admin",)))],
)
def academic_analytics(period: str | None = None, db: Session = Depends(get_db)):
    if period and not db.query(AcademicPeriod).filter_by(name=period).first():
        raise HTTPException(404, "Período no encontrado")
    query = db.query(Enrollment).filter(Enrollment.state.in_(("enrolled", "completed", "failed")))
    if period:
        query = query.filter(Enrollment.period == period)
    selected = query.all()
    relevant_students = {e.student_id for e in selected}
    open_alerts = db.query(EarlyAlert).filter_by(status="open").all()
    if period:
        open_alerts = [a for a in open_alerts if a.student_id in relevant_students]

    def metrics(enrollments):
        calculations = [academic_result(db, e) for e in enrollments]
        finals = [r for r in calculations if r.final and r.value is not None]
        provisionals = [r for r in calculations if not r.final and r.value is not None]
        ids = [e.enrollment_id for e in enrollments]
        attendance = (
            db.query(Attendance).filter(Attendance.enrollment_id.in_(ids)).all() if ids else []
        )
        return {
            "average_grade": round(sum(r.value for r in finals) / len(finals), 2)
            if finals
            else None,
            "grade_count": len(finals),
            "provisional_average_grade": round(
                sum(r.value for r in provisionals) / len(provisionals), 2
            )
            if provisionals
            else None,
            "provisional_grade_count": len(provisionals),
            "attendance_count": len(attendance),
            "attendance_percentage": percentage(sum(a.present for a in attendance), len(attendance))
            if attendance
            else None,
            "pass_rate": percentage(sum(r.status == "passed" for r in finals), len(finals))
            if finals
            else None,
        }

    career_metrics = []
    for career in db.query(Career).order_by(Career.name):
        members = [
            s
            for s in db.query(Student).filter_by(career_id=career.career_id)
            if not period or s.student_id in relevant_students
        ]
        ids = {s.student_id for s in members}
        active = sum(s.active for s in members)
        career_metrics.append(
            {
                "career_id": career.career_id,
                "career_code": career.code,
                "career_name": career.name,
                "student_count": len(members),
                "active_count": active,
                "retention_percentage": percentage(active, len(members)) if members else None,
                "open_alerts": sum(a.student_id in ids for a in open_alerts),
                **metrics([e for e in selected if e.student_id in ids]),
            }
        )
    subject_metrics = [
        {
            "subject_id": s.subject_id,
            "subject_code": s.code,
            "subject_name": s.description,
            "enrollments": len(
                rows := [e for e in selected if e.section.subject_id == s.subject_id]
            ),
            **metrics(rows),
        }
        for s in db.query(Subject).order_by(Subject.code)
    ]
    subject_metrics.sort(
        key=lambda r: (r["pass_rate"] is None, r["pass_rate"] or 0, r["subject_code"])
    )
    total = len(relevant_students) if period else db.query(Student).count()
    active = db.query(Student).filter(Student.active.is_(True))
    if period:
        active = active.filter(Student.student_id.in_(relevant_students))
    return {
        "period": period,
        "definitions": {
            "active_ratio": "Porcentaje de estudiantes marcados como activos; no mide permanencia entre períodos.",
            "grades": "Solo resultados finales publicados. Sin datos no equivale a cero.",
            "attendance": "Presencias computables sobre clases registradas; excluye selecciones retiradas y en espera.",
            "alerts": "Casos abiertos de estudiantes del período; no implica que se originaran en ese período.",
        },
        "risk_summary": {
            "students_at_risk": len({a.student_id for a in open_alerts}),
            "academic_alerts": sum(a.category == "academic" for a in open_alerts),
            "attendance_alerts": sum(a.category == "attendance" for a in open_alerts),
            "financial_alerts": sum(a.category == "financial" for a in open_alerts),
            "critical_alerts": sum(a.severity == "critical" for a in open_alerts),
            "unassigned_alerts": sum(a.assigned_to is None for a in open_alerts),
            "institutional_retention": percentage(active.count(), total) if total else None,
        },
        "career_metrics": career_metrics,
        "subject_metrics": subject_metrics,
    }
