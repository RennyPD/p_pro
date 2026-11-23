"""Section-scoped tasks, submissions and explicit draft grade transfer."""

import base64
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    ACADEMIC_SCOPE,
    calendar_audience,
    ensure_section_access,
    get_current_user,
    guardian_student_ids,
    has_permission,
    has_scope,
    require_permissions,
    require_personal,
)
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.enrollment_model import Enrollment
from app.models.grade_model import Grade, GradeChange
from app.models.operations_model import (
    Assignment,
    CalendarEvent,
    Submission,
    SubmissionAttachment,
    SubmissionRevision,
)
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.operations_schema import AssignmentCreate, SubmissionCreate, SubmissionGrade
from app.services.academic_grading import audit_event as log_event
from app.services.academic_grading import ensure_grading_open, write_grade
from app.services.academic_locks import (
    assignment_section,
    lock_assignment,
    lock_sections,
    lock_submission,
)
from app.services.business_time import business_date

router = APIRouter()


def manager(user: User = Depends(require_permissions("tasks.manage"))):
    return user


def grader(
    user: User = Depends(manager),
    permitted: User = Depends(require_permissions("grades.manage")),
):
    return user


def audit_event(db, user_id, action, resource, resource_id, detail):
    log_event(db, user_id, action, f"{resource}:{resource_id}", detail)


def utc(value):
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def scope(db, user):
    if has_scope(user, *ACADEMIC_SCOPE):
        return db.query(Section.section_id)
    if user.teacher_id:
        return db.query(Section.section_id).filter(Section.teacher_id == user.teacher_id)
    # Without a linked person the scope is empty, never "everything".
    ids = [user.student_id] if user.student_id else guardian_student_ids(db, user, "tasks")
    return db.query(Enrollment.section_id).filter(
        Enrollment.student_id.in_(ids), Enrollment.state.in_(["enrolled", "completed", "failed"])
    )


def visible(db, user, assignment_id):
    query = db.query(Assignment).filter(
        Assignment.assignment_id == assignment_id, Assignment.section_id.in_(scope(db, user))
    )
    if not has_permission(user, "tasks.manage"):
        query = query.filter(Assignment.published.is_(True))
    item = query.first()
    if not item:
        raise HTTPException(404, "Tarea no disponible")
    return item


def submission_view(db, item):
    if not item:
        return None
    return {
        "submission_id": item.submission_id,
        "assignment_id": item.assignment_id,
        "student_id": item.student_id,
        "content": item.content,
        "submitted_at": item.submitted_at,
        "status": item.status,
        "score": item.score,
        "feedback": item.feedback,
        "attempts": db.query(SubmissionRevision)
        .filter_by(submission_id=item.submission_id)
        .count(),
    }


def task_view(db, item, user):
    section = db.get(Section, item.section_id)
    own = (
        db.query(Submission)
        .filter_by(assignment_id=item.assignment_id, student_id=user.student_id)
        .first()
        if user.student_id
        else None
    )
    return {
        **AssignmentCreate.model_validate(item, from_attributes=True).model_dump(),
        "assignment_id": item.assignment_id,
        "subject_name": section.subject_name,
        "section_code": section.code,
        "teacher_name": section.teacher_name,
        "period_name": section.period_name,
        "submission": submission_view(db, own),
        "submission_count": db.query(Submission).filter_by(assignment_id=item.assignment_id).count()
        if has_permission(user, "tasks.manage")
        else None,
    }


@router.get("/task-sections")
def task_sections(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [
        {
            "section_id": s.section_id,
            "code": s.code,
            "subject_name": s.subject_name,
            "teacher_name": s.teacher_name,
            "period_name": s.period_name,
        }
        for s in db.query(Section)
        .filter(Section.section_id.in_(scope(db, user)))
        .order_by(Section.code)
    ]


@router.get("/agenda")
def agenda(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sections = {
        s.section_id: s for s in db.query(Section).filter(Section.section_id.in_(scope(db, user)))
    }
    events = db.query(CalendarEvent)
    if not has_scope(user, *ACADEMIC_SCOPE):
        events = events.filter(
            (
                (CalendarEvent.audience.in_(["all", calendar_audience(user)]))
                & CalendarEvent.section_id.is_(None)
            )
            | ((CalendarEvent.audience == "section") & CalendarEvent.section_id.in_(sections))
        )
    result = [
        {
            "id": f"event-{e.calendar_event_id}",
            "event_id": e.calendar_event_id,
            "kind": e.event_type,
            "title": e.title,
            "description": e.description,
            "starts_at": e.starts_at,
            "ends_at": e.ends_at,
            "section_id": e.section_id,
            "subject_name": sections[e.section_id].subject_name
            if e.section_id in sections
            else "Institución",
            "no_school": e.no_school,
            "audience": e.audience,
        }
        for e in events
    ]
    tasks = db.query(Assignment).filter(
        Assignment.section_id.in_(sections),
        Assignment.published.is_(True),
        Assignment.lifecycle != "archived",
    )
    result += [
        {
            "id": f"task-{t.assignment_id}",
            "assignment_id": t.assignment_id,
            "kind": "task",
            "title": t.title,
            "starts_at": t.due_at,
            "ends_at": t.due_at,
            "section_id": t.section_id,
            "subject_name": sections[t.section_id].subject_name,
        }
        for t in tasks
    ]
    result += [
        {
            "id": f"assessment-{a.assessment_id}",
            "kind": "assessment",
            "title": a.name,
            "starts_at": a.due_date.isoformat(),
            "ends_at": a.due_date.isoformat(),
            "section_id": a.section_id,
            "subject_name": sections[a.section_id].subject_name,
            "all_day": True,
        }
        for a in db.query(Assessment).filter(
            Assessment.section_id.in_(sections), Assessment.due_date.is_not(None)
        )
    ]
    return result


@router.get("/assignments")
def tasks(
    section_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Assignment).filter(Assignment.section_id.in_(scope(db, user)))
    if section_id:
        query = query.filter(Assignment.section_id == section_id)
    if not has_permission(user, "tasks.manage"):
        query = query.filter(Assignment.published.is_(True))
    return [task_view(db, item, user) for item in query.order_by(Assignment.due_at)]


def validate_task(db, user, data, existing=None):
    section = ensure_section_access(db, user, data.section_id)
    ensure_grading_open(db, section)
    if data.assessment_id:
        assessment = db.get(Assessment, data.assessment_id)
        if not assessment or assessment.section_id != data.section_id:
            raise HTTPException(422, "La evaluación debe pertenecer a la misma sección")
        if assessment.closed:
            raise HTTPException(409, "La evaluación está cerrada")
        # A single task per component avoids inventing an aggregation policy.
        conflict = db.query(Assignment).filter_by(assessment_id=data.assessment_id)
        if existing:
            conflict = conflict.filter(Assignment.assignment_id != existing.assignment_id)
        if conflict.first():
            raise HTTPException(409, "Esta evaluación ya está vinculada a otra tarea")
    if existing and db.query(Submission).filter_by(assignment_id=existing.assignment_id).first():
        if (existing.section_id, existing.assessment_id, existing.max_score) != (
            data.section_id,
            data.assessment_id,
            data.max_score,
        ):
            raise HTTPException(
                409, "Con entregas registradas no se cambia sección, evaluación ni escala"
            )


@router.post("/assignments")
def create_task(
    data: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(manager)
):
    lock_sections(db, data.section_id)
    validate_task(db, user, data)
    values = data.model_dump()
    values["due_at"] = utc(data.due_at)
    item = Assignment(**values, created_by=user.user_id)
    db.add(item)
    db.flush()
    audit_event(
        db, user.user_id, "assignment.created", "assignment", item.assignment_id, item.title
    )
    db.commit()
    return task_view(db, item, user)


@router.put("/assignments/{assignment_id}")
def edit_task(
    assignment_id: int,
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(manager),
):
    lock_sections(db, assignment_section(db, assignment_id), data.section_id)
    item = visible(db, user, assignment_id)
    validate_task(db, user, data, item)
    for key, value in data.model_dump().items():
        setattr(item, key, utc(value) if key == "due_at" else value)
    audit_event(
        db,
        user.user_id,
        "assignment.updated",
        "assignment",
        item.assignment_id,
        f"{item.title}: {item.lifecycle}",
    )
    db.commit()
    return task_view(db, item, user)


@router.post("/assignments/{assignment_id}/submit")
def submit(
    assignment_id: int,
    data: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_personal("records.own", "own")),
):
    lock_assignment(db, assignment_id)
    task = visible(db, user, assignment_id)
    enrollment = (
        db.query(Enrollment)
        .filter_by(section_id=task.section_id, student_id=user.student_id, state="enrolled")
        .first()
    )
    if not enrollment:
        raise HTTPException(403, "Solo estudiantes activos de la sección pueden entregar")
    ensure_grading_open(db, enrollment.section, enrollment)
    if task.lifecycle != "open":
        raise HTTPException(409, "La tarea está cerrada o archivada")
    if task.assessment_id and db.get(Assessment, task.assessment_id).closed:
        raise HTTPException(409, "La evaluación está cerrada")
    now = datetime.now(UTC).replace(tzinfo=None)
    if now > utc(task.due_at) and not task.allow_late:
        raise HTTPException(409, "El plazo de entrega terminó")
    item = (
        db.query(Submission)
        .filter_by(assignment_id=assignment_id, student_id=user.student_id)
        .first()
    )
    if item:
        if not task.allow_resubmit or item.score is not None:
            raise HTTPException(
                409, "No se admite reenvío después de calificar o cuando está deshabilitado"
            )
        if not db.query(SubmissionRevision).filter_by(submission_id=item.submission_id).first():
            db.add(
                SubmissionRevision(
                    submission_id=item.submission_id,
                    content=item.content,
                    submitted_at=item.submitted_at,
                )
            )
        item.content, item.submitted_at, item.status = data.content, now, "resubmitted"
        item.score, item.feedback = None, ""
    else:
        item = Submission(
            assignment_id=assignment_id,
            student_id=user.student_id,
            content=data.content,
            submitted_at=now,
        )
        db.add(item)
        db.flush()
    revision = SubmissionRevision(
        submission_id=item.submission_id, content=data.content, submitted_at=now
    )
    db.add(revision)
    if data.attachment:
        attachment = data.attachment
        signatures = {
            "application/pdf": (b"%PDF-", (".pdf",)),
            "image/png": (b"\x89PNG\r\n\x1a\n", (".png",)),
            "image/jpeg": (b"\xff\xd8\xff", (".jpg", ".jpeg")),
        }
        try:
            binary = base64.b64decode(attachment.content_base64, validate=True)
        except ValueError as exc:
            raise HTTPException(422, "Vuelve a seleccionar el archivo de entrega") from exc
        if len(binary) > 5 * 1024 * 1024:
            raise HTTPException(413, "El archivo de entrega supera 5 MB")
        signature, extensions = signatures[attachment.mime_type]
        filename = attachment.filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if (
            not filename.casefold().endswith(extensions)
            or not binary.startswith(signature)
            or any(ord(char) < 32 or ord(char) == 127 for char in filename)
        ):
            raise HTTPException(
                422, "Selecciona un PDF, PNG o JPEG con una extensión que coincida con su contenido"
            )
        db.flush()
        db.add(
            SubmissionAttachment(
                revision_id=revision.revision_id,
                filename=filename,
                mime_type=attachment.mime_type,
                content=binary,
            )
        )
    audit_event(
        db,
        user.user_id,
        "assignment.submitted",
        "assignment",
        task.assignment_id,
        f"Estudiante {user.student_id}",
    )
    db.commit()
    return submission_view(db, item)


@router.get("/assignments/{assignment_id}/submissions")
def roster(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    task = visible(db, user, assignment_id)
    rows = (
        db.query(Enrollment)
        .filter(
            Enrollment.section_id == task.section_id,
            Enrollment.state.in_(["enrolled", "completed", "failed"]),
        )
        .all()
    )
    return [
        {
            "student_id": e.student_id,
            "student_name": e.student.full_name,
            "enrollment_number": e.student.enrollment_number,
            "submission": submission_view(
                db,
                db.query(Submission)
                .filter_by(assignment_id=assignment_id, student_id=e.student_id)
                .first(),
            ),
        }
        for e in rows
    ]


@router.get("/submissions/{submission_id}/revisions")
def revisions(
    submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_attempt_access(db, user, submission_id)
    return [
        {
            "revision_id": r.revision_id,
            "content": r.content,
            "submitted_at": r.submitted_at,
            "filename": filename,
        }
        for r, filename in db.query(SubmissionRevision, SubmissionAttachment.filename)
        .outerjoin(
            SubmissionAttachment, SubmissionAttachment.revision_id == SubmissionRevision.revision_id
        )
        .filter(SubmissionRevision.submission_id == submission_id)
        .order_by(SubmissionRevision.revision_id)
    ]


def ensure_attempt_access(db, user, submission_id):
    item = db.get(Submission, submission_id)
    if not item:
        raise HTTPException(404, "Entrega no disponible")
    visible(db, user, item.assignment_id)
    if not has_permission(user, "tasks.manage") and user.student_id != item.student_id:
        raise HTTPException(403, "Solo puedes consultar tus propios intentos")


@router.get("/submissions/{submission_id}/revisions/{revision_id}/attachment")
def download_attempt_attachment(
    submission_id: int,
    revision_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_attempt_access(db, user, submission_id)
    revision = db.get(SubmissionRevision, revision_id)
    if revision is None or revision.submission_id != submission_id:
        raise HTTPException(404, "Adjunto de entrega no disponible")
    attachment = db.get(SubmissionAttachment, revision_id)
    if attachment is None:
        raise HTTPException(404, "Este intento no contiene un adjunto")
    return Response(
        attachment.content,
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.filename, safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/submissions/{submission_id}/grade")
def grade(
    submission_id: int,
    data: SubmissionGrade,
    db: Session = Depends(get_db),
    user: User = Depends(manager),
):
    lock_submission(db, submission_id)
    item = db.get(Submission, submission_id)
    if not item:
        raise HTTPException(404, "Entrega no disponible")
    task = visible(db, user, item.assignment_id)
    ensure_grading_open(db, db.get(Section, task.section_id))
    if task.lifecycle == "archived":
        raise HTTPException(409, "La tarea está archivada")
    if data.score > task.max_score:
        raise HTTPException(422, "La puntuación supera el máximo de la tarea")
    if task.assessment_id and db.get(Assessment, task.assessment_id).closed:
        raise HTTPException(409, "La evaluación está cerrada")
    item.score, item.feedback, item.status = data.score, data.feedback, "graded"
    audit_event(
        db,
        user.user_id,
        "assignment.graded",
        "assignment",
        task.assignment_id,
        f"Entrega {item.submission_id}: {data.score}/{task.max_score}",
    )
    db.commit()
    return submission_view(db, item)


class TransferRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=250)


@router.post("/assignments/{assignment_id}/transfer-grades")
def transfer(
    assignment_id: int,
    data: TransferRequest,
    db: Session = Depends(get_db),
    user: User = Depends(grader),
):
    lock_assignment(db, assignment_id)
    task = visible(db, user, assignment_id)
    if len(data.reason.strip()) < 2:
        raise HTTPException(422, "Indica el motivo de la transferencia")
    if not task.assessment_id or task.lifecycle == "archived":
        raise HTTPException(409, "Selecciona una tarea calificable no archivada")
    assessment = db.get(Assessment, task.assessment_id)
    ensure_grading_open(db, db.get(Section, task.section_id))
    if assessment.closed:
        raise HTTPException(409, "La evaluación está cerrada")
    submissions = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id, Submission.score.is_not(None))
        .all()
    )
    if not submissions:
        raise HTTPException(409, "No hay entregas calificadas")
    # Never silently overwrite an existing independent or published grade.
    prepared = []
    skipped = 0
    for item in submissions:
        enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.section_id == task.section_id,
                Enrollment.student_id == item.student_id,
                Enrollment.state.in_(["enrolled", "completed", "failed"]),
            )
            .first()
        )
        if not enrollment:
            continue
        existing = (
            db.query(Grade)
            .filter_by(
                enrollment_id=enrollment.enrollment_id, assessment_id=assessment.assessment_id
            )
            .first()
        )
        if existing:
            origin = (
                db.query(GradeChange)
                .filter(
                    GradeChange.grade_id == existing.grade_id,
                    GradeChange.action == "created",
                    GradeChange.reason.startswith(f"[Tarea {assignment_id}] "),
                )
                .first()
            )
            if (
                origin
                and existing.grade_value == round(item.score * 100 / task.max_score, 2)
                and existing.status in {"draft", "published"}
            ):
                skipped += 1
                continue
            raise HTTPException(
                409,
                "Ya existen notas diferentes en esta evaluación. Revísalas en Evaluaciones; no se sobrescriben automáticamente",
            )
        prepared.append((enrollment, item))
    for enrollment, item in prepared:
        write_grade(
            db,
            enrollment,
            assessment,
            round(item.score * 100 / task.max_score, 2),
            assessment.name,
            business_date(),
            "draft",
            user.user_id,
            f"[Tarea {assignment_id}] {data.reason.strip()}"[:250],
        )
    audit_event(
        db,
        user.user_id,
        "assignment.transferred",
        "assignment",
        task.assignment_id,
        data.reason.strip(),
    )
    db.commit()
    return {"transferred": len(prepared), "skipped": skipped, "status": "draft"}
