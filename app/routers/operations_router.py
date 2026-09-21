import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import (
    ensure_section_access,
    ensure_student_academic_access,
    get_current_user,
    is_admin,
    require_roles,
)
from app.db.Session import get_db
from app.models.attendance_model import Attendance
from app.models.career_model import Career
from app.models.community_model import StudentGuardian
from app.models.enrollment_model import Enrollment
from app.models.finance_model import Charge, Payment, StudentAccount
from app.models.grade_model import Grade
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
from app.models.user_model import User
from app.schemas.operations_schema import (
    AdmissionCreate,
    AdmissionOut,
    AdmissionUpdate,
    AlertCreate,
    AlertAssignment,
    AlertInterventionCreate,
    AlertInterventionOut,
    AlertOut,
    AlertResolve,
    ApprovalCreate,
    ApprovalOut,
    ApprovalResolve,
    AssignmentCreate,
    AssignmentOut,
    CalendarEventCreate,
    CalendarEventOut,
    LessonPlanCreate,
    LessonPlanOut,
    StudentDocumentCreate,
    StudentDocumentOut,
    SubmissionCreate,
    SubmissionGrade,
    SubmissionOut,
)
from app.schemas.student_schema import StudentCreate
from app.services.student_service import create_student_service

router = APIRouter(prefix="/operations", tags=["institutional operations"])


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
        section_ids = []
        if user.teacher_id:
            section_ids = [
                row[0]
                for row in db.query(Section.section_id).filter(
                    Section.teacher_id == user.teacher_id
                )
            ]
        elif user.student_id:
            section_ids = [
                row[0]
                for row in db.query(Enrollment.section_id).filter(
                    Enrollment.student_id == user.student_id
                )
            ]
        query = query.filter(
            (CalendarEvent.audience.in_(["all", role]))
            | (CalendarEvent.section_id.in_(section_ids))
        )
    return query.order_by(CalendarEvent.starts_at).all()


@router.post("/calendar", response_model=CalendarEventOut)
def create_event(
    data: CalendarEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    if not is_admin(user):
        if data.audience != "section":
            raise HTTPException(status_code=403, detail="Teachers can only create section events")
        ensure_section_access(db, user, data.section_id or 0)
    item = CalendarEvent(**data.model_dump(), created_by=user.user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/lesson-plans", response_model=list[LessonPlanOut])
def lesson_plans(
    section_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
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
    user: User = Depends(require_roles("admin", "teacher")),
):
    section = ensure_section_access(db, user, data.section_id)
    item = LessonPlan(**data.model_dump(), teacher_id=section.teacher_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/assignments", response_model=list[AssignmentOut])
def assignments(
    section_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Assignment)
    if section_id:
        ensure_section_access(db, user, section_id, allow_student=True)
        query = query.filter(Assignment.section_id == section_id)
    elif user.student_id:
        sections = db.query(Enrollment.section_id).filter(Enrollment.student_id == user.student_id)
        query = query.filter(Assignment.section_id.in_(sections), Assignment.published.is_(True))
    elif user.teacher_id:
        sections = db.query(Section.section_id).filter(Section.teacher_id == user.teacher_id)
        query = query.filter(Assignment.section_id.in_(sections))
    elif user.guardian_id:
        student_ids = db.query(StudentGuardian.student_id).filter(
            StudentGuardian.guardian_id == user.guardian_id
        )
        sections = db.query(Enrollment.section_id).filter(Enrollment.student_id.in_(student_ids))
        query = query.filter(Assignment.section_id.in_(sections), Assignment.published.is_(True))
    elif not is_admin(user):
        query = query.filter(False)
    return query.order_by(Assignment.due_at).all()


@router.post("/assignments", response_model=AssignmentOut)
def create_assignment(
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    ensure_section_access(db, user, data.section_id)
    item = Assignment(**data.model_dump(), created_by=user.user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/assignments/{assignment_id}/submit", response_model=SubmissionOut)
def submit_assignment(
    assignment_id: int,
    data: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or not assignment.published:
        raise HTTPException(status_code=404, detail="Assignment not found")
    ensure_section_access(db, user, assignment.section_id, allow_student=True)
    item = (
        db.query(Submission)
        .filter_by(assignment_id=assignment_id, student_id=user.student_id)
        .first()
    )
    if item is None:
        item = Submission(
            assignment_id=assignment_id, student_id=user.student_id, content=data.content
        )
        db.add(item)
    else:
        item.content = data.content
        item.submitted_at = datetime.now(UTC).replace(tzinfo=None)
        item.status = "resubmitted"
    db.commit()
    db.refresh(item)
    return item


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionOut])
def assignment_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    ensure_section_access(db, user, assignment.section_id)
    return db.query(Submission).filter_by(assignment_id=assignment_id).all()


@router.patch("/submissions/{submission_id}/grade", response_model=SubmissionOut)
def grade_submission(
    submission_id: int,
    data: SubmissionGrade,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    item = db.get(Submission, submission_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = db.get(Assignment, item.assignment_id)
    ensure_section_access(db, user, assignment.section_id)
    if data.score > assignment.max_score:
        raise HTTPException(status_code=422, detail="Score exceeds assignment maximum")
    item.score = data.score
    item.feedback = data.feedback
    item.status = "graded"
    db.commit()
    db.refresh(item)
    return item


@router.get("/alerts", response_model=list[AlertOut])
def alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(EarlyAlert)
    ids = student_scope_ids(db, user)
    if ids is not None:
        query = query.filter(EarlyAlert.student_id.in_(ids))
    return query.order_by(EarlyAlert.created_at.desc()).all()


@router.post("/alerts", response_model=AlertOut)
def create_alert(
    data: AlertCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    ensure_student_academic_access(db, user, data.student_id)
    item = EarlyAlert(**data.model_dump(), created_by=user.user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/alerts/{alert_id}/assignment", response_model=AlertOut)
def assign_alert(
    alert_id: int,
    data: AlertAssignment,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    item = db.get(EarlyAlert, alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, item.student_id)
    if data.assigned_to is not None and db.get(User, data.assigned_to) is None:
        raise HTTPException(status_code=422, detail="Assigned user not found")
    item.assigned_to = data.assigned_to
    item.follow_up_date = data.follow_up_date
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
    return (
        db.query(AlertIntervention)
        .filter_by(early_alert_id=alert_id)
        .order_by(AlertIntervention.created_at.desc())
        .all()
    )


@router.post("/alerts/{alert_id}/interventions", response_model=AlertInterventionOut)
def add_alert_intervention(
    alert_id: int,
    data: AlertInterventionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    alert = db.get(EarlyAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, alert.student_id)
    item = AlertIntervention(
        early_alert_id=alert_id,
        performed_by=user.user_id,
        **data.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/alerts/generate", dependencies=[Depends(require_roles("admin"))])
def generate_alerts(db: Session = Depends(get_db)):
    created = 0
    for student in db.query(Student).filter(Student.active.is_(True)).all():
        grades = [
            row[0]
            for row in db.query(Grade.grade_value)
            .join(Enrollment)
            .filter(Enrollment.student_id == student.student_id)
        ]
        attendance_rows = (
            db.query(Attendance.present)
            .join(Enrollment)
            .filter(Enrollment.student_id == student.student_id)
            .all()
        )
        account = db.query(StudentAccount).filter_by(student_id=student.student_id).first()
        checks = []
        if grades and sum(grades) / len(grades) < 70:
            checks.append(("academic", "high", "Promedio acumulado inferior a 70"))
        if (
            attendance_rows
            and sum(bool(row[0]) for row in attendance_rows) / len(attendance_rows) < 0.8
        ):
            checks.append(("attendance", "high", "Asistencia acumulada inferior al 80%"))
        if (
            account
            and sum(c.amount for c in account.charges) - sum(p.amount for p in account.payments) > 0
        ):
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
                    )
                )
                created += 1
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
    user: User = Depends(require_roles("admin", "teacher")),
):
    item = db.get(EarlyAlert, alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_student_academic_access(db, user, item.student_id)
    item.status = "resolved"
    item.resolution_notes = data.resolution_notes if data else ""
    item.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(item)
    return item


@router.get("/guardian/overview")
def guardian_overview(
    db: Session = Depends(get_db), user: User = Depends(require_roles("guardian"))
):
    ids = student_scope_ids(db, user) or []
    return [
        {
            "student_id": s.student_id,
            "student_name": f"{s.first_name} {s.last_name}",
            "enrollment_number": s.enrollment_number,
            "open_alerts": db.query(EarlyAlert)
            .filter_by(student_id=s.student_id, status="open")
            .count(),
        }
        for s in db.query(Student).filter(Student.student_id.in_(ids)).all()
    ]


@router.get(
    "/admissions", response_model=list[AdmissionOut], dependencies=[Depends(require_roles("admin"))]
)
def admissions(db: Session = Depends(get_db)):
    return db.query(AdmissionApplication).order_by(AdmissionApplication.created_at.desc()).all()


@router.post(
    "/admissions", response_model=AdmissionOut, dependencies=[Depends(require_roles("admin"))]
)
def create_admission(data: AdmissionCreate, db: Session = Depends(get_db)):
    item = AdmissionApplication(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/admissions/{application_id}",
    response_model=AdmissionOut,
    dependencies=[Depends(require_roles("admin"))],
)
def update_admission(application_id: int, data: AdmissionUpdate, db: Session = Depends(get_db)):
    item = db.get(AdmissionApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/admissions/{application_id}/enroll",
    dependencies=[Depends(require_roles("admin"))],
)
def enroll_admission(application_id: int, db: Session = Depends(get_db)):
    item = db.get(AdmissionApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if item.status == "enrolled":
        raise HTTPException(status_code=409, detail="Application was already enrolled")
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
    )
    item.status = "enrolled"
    db.commit()
    return {"student_id": student.student_id, "enrollment_number": student.enrollment_number}


@router.get(
    "/approvals", response_model=list[ApprovalOut], dependencies=[Depends(require_roles("admin"))]
)
def approvals(db: Session = Depends(get_db)):
    return db.query(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()).all()


@router.post("/approvals", response_model=ApprovalOut)
def request_approval(
    data: ApprovalCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    item = ApprovalRequest(**data.model_dump(), requested_by=user.user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/approvals/{request_id}", response_model=ApprovalOut)
def resolve_approval(
    request_id: int,
    data: ApprovalResolve,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    item = db.get(ApprovalRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    item.status = data.status
    item.resolution_notes = data.resolution_notes
    item.resolved_by = user.user_id
    item.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(item)
    return item


@router.get("/students/{student_id}/documents", response_model=list[StudentDocumentOut])
def documents(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_academic_access(db, user, student_id)
    return db.query(StudentDocument).filter_by(student_id=student_id).all()


@router.post("/students/{student_id}/documents", response_model=StudentDocumentOut)
def upload_document(
    student_id: int,
    data: StudentDocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    try:
        content = base64.b64decode(data.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid base64 content") from exc
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Document exceeds 5 MB")
    item = StudentDocument(
        student_id=student_id,
        document_type=data.document_type,
        filename=data.filename,
        mime_type=data.mime_type,
        content=content,
        expires_on=data.expires_on,
        uploaded_by=user.user_id,
    )
    db.add(item)
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
        headers={"Content-Disposition": f'attachment; filename="{item.filename}"'},
    )


@router.get("/analytics/summary", dependencies=[Depends(require_roles("admin"))])
def analytics(db: Session = Depends(get_db)):
    students = db.query(Student).count()
    active = db.query(Student).filter(Student.active.is_(True)).count()
    enrollments = db.query(Enrollment).count()
    grades = [r[0] for r in db.query(Grade.grade_value).all()]
    charges = db.query(func.coalesce(func.sum(Charge.amount), 0)).scalar()
    payments = db.query(func.coalesce(func.sum(Payment.amount), 0)).scalar()
    return {
        "students": students,
        "active_students": active,
        "enrollments": enrollments,
        "average_grade": round(sum(grades) / len(grades), 2) if grades else 0,
        "open_alerts": db.query(EarlyAlert).filter_by(status="open").count(),
        "receivables": round(float(charges) - float(payments), 2),
        "admission_pipeline": db.query(AdmissionApplication)
        .filter(AdmissionApplication.status.notin_(["rejected", "enrolled"]))
        .count(),
    }


def percentage(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) * 100 / float(denominator), 2) if denominator else 0


@router.get("/analytics/academic", dependencies=[Depends(require_roles("admin"))])
def academic_analytics(db: Session = Depends(get_db)):
    open_alerts = db.query(EarlyAlert).filter_by(status="open").all()
    career_metrics = []
    for career in db.query(Career).order_by(Career.name).all():
        student_ids = [
            row[0]
            for row in db.query(Student.student_id).filter(Student.career_id == career.career_id)
        ]
        active = (
            db.query(Student)
            .filter(Student.career_id == career.career_id, Student.active.is_(True))
            .count()
        )
        grades = []
        attendance = []
        if student_ids:
            grades = [
                row[0]
                for row in db.query(Grade.grade_value)
                .join(Enrollment)
                .filter(Enrollment.student_id.in_(student_ids))
            ]
            attendance = [
                bool(row[0])
                for row in db.query(Attendance.present)
                .join(Enrollment)
                .filter(Enrollment.student_id.in_(student_ids))
            ]
        career_metrics.append(
            {
                "career_id": career.career_id,
                "career_code": career.code,
                "career_name": career.name,
                "student_count": len(student_ids),
                "active_count": active,
                "retention_percentage": percentage(active, len(student_ids)),
                "average_grade": round(sum(grades) / len(grades), 2) if grades else 0,
                "attendance_percentage": percentage(sum(attendance), len(attendance)),
                "open_alerts": sum(a.student_id in student_ids for a in open_alerts),
            }
        )

    subject_metrics = []
    for subject in db.query(Subject).order_by(Subject.code).all():
        enrollment_ids = [
            row[0]
            for row in db.query(Enrollment.enrollment_id)
            .join(Section)
            .filter(Section.subject_id == subject.subject_id)
        ]
        grades = []
        attendance = []
        if enrollment_ids:
            grades = [
                row[0]
                for row in db.query(Grade.grade_value).filter(
                    Grade.enrollment_id.in_(enrollment_ids)
                )
            ]
            attendance = [
                bool(row[0])
                for row in db.query(Attendance.present).filter(
                    Attendance.enrollment_id.in_(enrollment_ids)
                )
            ]
        subject_metrics.append(
            {
                "subject_id": subject.subject_id,
                "subject_code": subject.code,
                "subject_name": subject.description,
                "enrollments": len(enrollment_ids),
                "average_grade": round(sum(grades) / len(grades), 2) if grades else 0,
                "pass_rate": percentage(sum(value >= 70 for value in grades), len(grades)),
                "attendance_percentage": percentage(sum(attendance), len(attendance)),
            }
        )
    subject_metrics.sort(key=lambda row: (row["pass_rate"], row["average_grade"]))

    total_students = db.query(Student).count()
    active_students = db.query(Student).filter(Student.active.is_(True)).count()
    return {
        "risk_summary": {
            "students_at_risk": len({alert.student_id for alert in open_alerts}),
            "academic_alerts": sum(alert.category == "academic" for alert in open_alerts),
            "attendance_alerts": sum(alert.category == "attendance" for alert in open_alerts),
            "financial_alerts": sum(alert.category == "financial" for alert in open_alerts),
            "critical_alerts": sum(alert.severity == "critical" for alert in open_alerts),
            "unassigned_alerts": sum(alert.assigned_to is None for alert in open_alerts),
            "institutional_retention": percentage(active_students, total_students),
        },
        "career_metrics": career_metrics,
        "subject_metrics": subject_metrics,
    }
