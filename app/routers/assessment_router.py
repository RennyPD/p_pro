from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    ensure_enrollment_access,
    ensure_section_access,
    get_current_user,
    is_admin,
    require_permissions,
)
from app.db.Session import get_db
from app.models.assessment_model import Assessment, AssessmentTemplate
from app.models.enrollment_model import Enrollment
from app.models.subject_model import Subject
from app.models.user_model import User
from app.schemas.assessment_schema import (
    AssessmentCreate,
    AssessmentOut,
    AssessmentTemplateApply,
    AssessmentTemplateCreate,
    AssessmentTemplateOut,
    AssessmentUpdate,
    DistributionUpdate,
    FinalGradeOut,
    PlanTemplateCreate,
    PlanTemplateOut,
    ReasonRequest,
)
from app.services.academic_grading import academic_result, audit_event, ensure_grading_open

router = APIRouter(prefix="/assessments", tags=["weighted assessments"])
assessment_manager = require_permissions("grades.manage", fallback_roles=("admin", "teacher"))


@router.get("/templates", response_model=list[AssessmentTemplateOut])
def assessment_templates(db: Session = Depends(get_db), user: User = Depends(assessment_manager)):
    return (
        db.query(AssessmentTemplate)
        .filter_by(owner_id=user.user_id)
        .filter(AssessmentTemplate.components.is_(None))
        .order_by(AssessmentTemplate.name)
        .all()
    )


@router.post("/templates", response_model=AssessmentTemplateOut)
def create_assessment_template(
    data: AssessmentTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    item = AssessmentTemplate(owner_id=user.user_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/templates/{template_id}/apply", response_model=AssessmentOut)
def apply_assessment_template(
    template_id: int,
    data: AssessmentTemplateApply,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    template = db.get(AssessmentTemplate, template_id)
    if template is None or template.owner_id != user.user_id:
        raise HTTPException(status_code=404, detail="Assessment template not found")
    section = ensure_section_access(db, user, data.section_id)
    ensure_grading_open(db, section)
    validate_total_weight(db, data.section_id, template.weight)
    item = Assessment(
        section_id=data.section_id,
        name=template.name,
        weight=template.weight,
        due_date=data.due_date,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def ensure_assessment_writer(db: Session, user: User, assessment: Assessment) -> None:
    ensure_section_access(db, user, assessment.section_id)


def validate_total_weight(
    db: Session, section_id: int, weight: float, exclude_id: int | None = None
) -> None:
    query = db.query(Assessment).filter(Assessment.section_id == section_id)
    if exclude_id is not None:
        query = query.filter(Assessment.assessment_id != exclude_id)
    total = sum(item.weight for item in query.all()) + weight
    if total > 100.001:
        raise HTTPException(status_code=422, detail="Assessment weights cannot exceed 100%")


@router.get("/sections/{section_id}", response_model=list[AssessmentOut])
def list_assessments(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id, allow_student=True)
    return (
        db.query(Assessment)
        .filter(Assessment.section_id == section_id)
        .order_by(Assessment.due_date, Assessment.assessment_id)
        .all()
    )


@router.post("/", response_model=AssessmentOut)
def create_assessment(
    data: AssessmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    section = ensure_section_access(db, user, data.section_id)
    ensure_grading_open(db, section)
    validate_total_weight(db, data.section_id, data.weight)
    assessment = Assessment(**data.model_dump())
    db.add(assessment)
    db.flush()
    audit_event(
        db,
        user.user_id,
        "assessment.created",
        f"assessment:{assessment.assessment_id}",
        f"{assessment.name}; peso={assessment.weight}%",
    )
    db.commit()
    db.refresh(assessment)
    return assessment


@router.patch("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: int,
    data: AssessmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    ensure_assessment_writer(db, user, assessment)
    ensure_grading_open(db, assessment.section)
    if assessment.closed:
        raise HTTPException(status_code=409, detail="Closed assessments cannot be modified")
    values = data.model_dump(exclude_unset=True)
    if any(values.get(field, "present") is None for field in ("name", "weight")):
        raise HTTPException(status_code=422, detail="Nombre y porcentaje no pueden ser nulos")
    if "weight" in values:
        validate_total_weight(db, assessment.section_id, values["weight"], assessment_id)
    for key, value in values.items():
        setattr(assessment, key, value)
    audit_event(db, user.user_id, "assessment.updated", f"assessment:{assessment_id}", str(values))
    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("/{assessment_id}/close", response_model=AssessmentOut)
def close_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    ensure_assessment_writer(db, user, assessment)
    ensure_grading_open(db, assessment.section)
    enrollment_ids = {
        item.enrollment_id
        for item in db.query(Enrollment)
        .filter(
            Enrollment.section_id == assessment.section_id,
            Enrollment.state.in_(("enrolled", "completed", "failed")),
        )
        .all()
    }
    published_ids = {
        grade.enrollment_id for grade in assessment.grades if grade.status == "published"
    }
    pending = enrollment_ids - published_ids
    if pending:
        raise HTTPException(
            status_code=409,
            detail=f"Faltan notas publicadas de {len(pending)} estudiantes inscritos activos",
        )
    assessment.closed = True
    audit_event(
        db,
        user.user_id,
        "assessment.closed",
        f"assessment:{assessment_id}",
        "Cierre con notas publicadas completas",
    )
    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("/{assessment_id}/reopen", response_model=AssessmentOut)
def reopen_assessment(
    assessment_id: int,
    data: ReasonRequest,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only an admin can reopen an assessment")
    ensure_grading_open(db, assessment.section, allow_closed_section=True)
    if assessment.section.status == "closed":
        assessment.section.status = "active"
        audit_event(
            db,
            user.user_id,
            "assessment.section.reopened",
            f"section:{assessment.section_id}",
            data.reason,
        )
    assessment.closed = False
    audit_event(db, user.user_id, "assessment.reopened", f"assessment:{assessment_id}", data.reason)
    db.commit()
    db.refresh(assessment)
    return assessment


def final_grade(db: Session, enrollment: Enrollment) -> FinalGradeOut:
    result = academic_result(db, enrollment)
    return FinalGradeOut(
        enrollment_id=enrollment.enrollment_id,
        student_id=enrollment.student_id,
        student_name=f"{enrollment.student.first_name} {enrollment.student.last_name}",
        weighted_grade=result.value or 0,
        completed_weight=round(result.completed_weight, 2),
        configured_weight=round(result.configured_weight, 2),
        calculation_mode=result.mode,
        final=result.final,
        status=result.status,
    )


@router.get("/enrollments/{enrollment_id}/final", response_model=FinalGradeOut)
def enrollment_final_grade(
    enrollment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enrollment = ensure_enrollment_access(db, user, enrollment_id)
    return final_grade(db, enrollment)


@router.get("/sections/{section_id}/finals", response_model=list[FinalGradeOut])
def section_final_grades(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id)
    enrollments = (
        db.query(Enrollment)
        .filter(
            Enrollment.section_id == section_id,
            Enrollment.state != "waitlisted",
            Enrollment.state != "withdrawn",
        )
        .all()
    )
    return [final_grade(db, item) for item in enrollments]


@router.patch("/sections/{section_id}/distribution", response_model=list[AssessmentOut])
def update_distribution(
    section_id: int,
    data: DistributionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    section = ensure_section_access(db, user, section_id)
    ensure_grading_open(db, section)
    assessments = db.query(Assessment).filter_by(section_id=section_id).all()
    ids = [item.assessment_id for item in data.components]
    if len(set(ids)) != len(ids) or set(ids) != {item.assessment_id for item in assessments}:
        raise HTTPException(
            status_code=422, detail="Incluye cada evaluación de la sección una sola vez"
        )
    if abs(sum(item.weight for item in data.components) - 100) > 0.001:
        raise HTTPException(status_code=422, detail="La distribución completa debe sumar 100%")
    weights = {item.assessment_id: item.weight for item in data.components}
    if any(item.closed and item.weight != weights[item.assessment_id] for item in assessments):
        raise HTTPException(
            status_code=409,
            detail="Reabre las evaluaciones cerradas antes de modificar sus porcentajes",
        )
    previous = {item.assessment_id: item.weight for item in assessments}
    for item in assessments:
        item.weight = weights[item.assessment_id]
    audit_event(
        db,
        user.user_id,
        "assessment.distribution",
        f"section:{section_id}",
        f"{data.reason}; antes={previous}; después={weights}",
    )
    db.commit()
    return assessments


def can_use_plan(db: Session, user: User, template: AssessmentTemplate):
    owner = db.get(User, template.owner_id)
    return template.owner_id == user.user_id or (owner is not None and is_admin(owner))


@router.get("/plans/templates", response_model=list[PlanTemplateOut])
def plan_templates(
    subject_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    query = db.query(AssessmentTemplate).filter(AssessmentTemplate.components.is_not(None))
    if subject_id is not None:
        query = query.filter_by(subject_id=subject_id)
    return [
        item
        for item in query.order_by(AssessmentTemplate.name).all()
        if can_use_plan(db, user, item)
    ]


@router.post("/plans/templates", response_model=PlanTemplateOut)
def save_plan_template(
    data: PlanTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    if db.get(Subject, data.subject_id) is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")
    template = db.query(AssessmentTemplate).filter_by(owner_id=user.user_id, name=data.name).first()
    if template is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una plantilla con ese nombre. Usa otro nombre para conservar la versión anterior.",
        )
    if template is None:
        template = AssessmentTemplate(owner_id=user.user_id, name=data.name)
        db.add(template)
    template.subject_id = data.subject_id
    template.weight = 100
    template.components = [
        {"name": item.name.strip(), "weight": item.weight} for item in data.components
    ]
    audit_event(db, user.user_id, "assessment.plan.saved", f"subject:{data.subject_id}", data.name)
    db.commit()
    return template


@router.post("/plans/templates/{template_id}/apply", response_model=list[AssessmentOut])
def apply_plan(
    template_id: int,
    data: AssessmentTemplateApply,
    db: Session = Depends(get_db),
    user: User = Depends(assessment_manager),
):
    template = db.get(AssessmentTemplate, template_id)
    if template is None or not template.components or not can_use_plan(db, user, template):
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    section = ensure_section_access(db, user, data.section_id)
    ensure_grading_open(db, section)
    if section.subject_id != template.subject_id:
        raise HTTPException(status_code=422, detail="La plantilla pertenece a otra asignatura")
    if db.query(Assessment).filter_by(section_id=data.section_id).first():
        raise HTTPException(
            status_code=409,
            detail="La sección ya tiene evaluaciones; no se reemplazará su plan automáticamente",
        )
    items = [
        Assessment(section_id=data.section_id, name=item["name"], weight=item["weight"])
        for item in template.components
    ]
    db.add_all(items)
    audit_event(
        db, user.user_id, "assessment.plan.applied", f"section:{data.section_id}", template.name
    )
    db.commit()
    return items


@router.get("/sections/{section_id}/audit")
def assessment_audit(
    section_id: int, db: Session = Depends(get_db), user: User = Depends(assessment_manager)
):
    from app.models.security_model import AuditLog

    ensure_section_access(db, user, section_id)
    resources = [f"section:{section_id}"] + [
        f"assessment:{item.assessment_id}"
        for item in db.query(Assessment).filter_by(section_id=section_id).all()
    ]
    return [
        {
            "action": item.action,
            "detail": item.detail,
            "created_at": item.created_at,
            "user_id": item.user_id,
            "actor": db.get(User, item.user_id).username
            if item.user_id and db.get(User, item.user_id)
            else "Sistema",
        }
        for item in db.query(AuditLog)
        .filter(AuditLog.resource.in_(resources))
        .order_by(AuditLog.created_at.desc())
        .limit(100)
        .all()
    ]
