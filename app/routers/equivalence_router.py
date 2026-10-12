from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions, require_roles
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.curriculum_model import CurriculumCourse
from app.models.governance_model import CourseEquivalence
from app.models.security_model import AuditLog
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.user_model import User
from app.schemas.governance_schema import EquivalenceCreate, EquivalenceOut, EquivalenceUpdate
from app.services.academic_grading import audit_event
from app.services.academic_recognition import current_courses, recognize

router = APIRouter()


def manager(
    user: User = Depends(require_roles("admin")),
    permitted: User = Depends(require_permissions("academic.manage", fallback_roles=("admin",))),
):
    return user


def output(db, item):
    career, source, target = (
        db.get(Career, item.career_id),
        db.get(Subject, item.source_subject_id),
        db.get(Subject, item.target_subject_id),
    )
    return EquivalenceOut(
        **{k: getattr(item, k) for k in EquivalenceCreate.model_fields if k != "reason"},
        course_equivalence_id=item.course_equivalence_id,
        source_code=source.code,
        source_name=source.description,
        target_code=target.code,
        target_name=target.description,
        career_name=career.name,
        career_code=career.code,
        created_by=item.created_by,
        updated_by=item.updated_by,
        updated_at=item.updated_at,
    )


def get_rule(db, identifier):
    item = db.get(CourseEquivalence, identifier)
    if not item:
        raise HTTPException(404, "Regla no encontrada")
    return item


def validate(db, data, exclude=None):
    if data.source_subject_id == data.target_subject_id:
        raise HTTPException(422, "Origen y destino deben ser diferentes")
    if (
        not db.get(Career, data.career_id)
        or not db.get(Subject, data.source_subject_id)
        or not db.get(Subject, data.target_subject_id)
    ):
        raise HTTPException(404, "Carrera o asignatura no encontrada")
    target = (
        db.query(CurriculumCourse)
        .filter_by(
            career_id=data.career_id,
            subject_id=data.target_subject_id,
            curriculum_version=data.curriculum_version,
        )
        .first()
    )
    if not target:
        raise HTTPException(
            422, "La asignatura destino debe pertenecer al pensum y versión seleccionados"
        )
    rows = (
        db.query(CourseEquivalence)
        .filter_by(career_id=data.career_id, curriculum_version=data.curriculum_version)
        .all()
    )
    rows = [r for r in rows if r.course_equivalence_id != exclude]
    if any(
        (r.source_subject_id, r.target_subject_id)
        == (data.source_subject_id, data.target_subject_id)
        for r in rows
    ):
        raise HTTPException(409, "La regla ya existe en esta carrera y versión; consulta su estado")
    if data.active:
        graph = {}
        for row in rows:
            if row.active:
                graph.setdefault(row.source_subject_id, set()).add(row.target_subject_id)
        pending, visited = [data.target_subject_id], set()
        while pending:
            node = pending.pop()
            if node == data.source_subject_id:
                raise HTTPException(409, "La activación produciría un ciclo de equivalencias")
            if node not in visited:
                visited.add(node)
                pending.extend(graph.get(node, []))


def impact(db, candidate, exclude=None):
    rules = db.query(CourseEquivalence).filter_by(career_id=candidate.career_id).all()
    after_rules = [r for r in rules if r.course_equivalence_id != exclude] + [candidate]
    items, affected, gained, lost = [], 0, 0, 0
    for student in (
        db.query(Student).filter_by(career_id=candidate.career_id).order_by(Student.student_id)
    ):
        before, after = recognize(db, student, rules), recognize(db, student, after_rules)
        new, removed = after.completed - before.completed, before.completed - after.completed
        if not new and not removed:
            continue
        affected += 1
        gained += len(new)
        lost += len(removed)
        if len(items) < 100:
            credits = {c.subject_id: c.credits for c in current_courses(db, student)}
            items.append(
                {
                    "student_id": student.student_id,
                    "student_name": student.full_name,
                    "enrollment_number": student.enrollment_number,
                    "gained": [db.get(Subject, sid).code for sid in sorted(new)],
                    "lost": [db.get(Subject, sid).code for sid in sorted(removed)],
                    "credit_delta": sum(credits.get(s, 0) for s in new)
                    - sum(credits.get(s, 0) for s in removed),
                }
            )
    return {
        "affected_students": affected,
        "gained_subjects": gained,
        "lost_subjects": lost,
        "students": items,
        "truncated": affected > len(items),
        "active_version": db.get(Career, candidate.career_id).curriculum_version,
        "applies_to_current_version": candidate.curriculum_version
        == db.get(Career, candidate.career_id).curriculum_version,
    }


@router.get("/equivalences", response_model=list[EquivalenceOut])
def list_rules(
    career_id: int | None = None,
    version: str | None = None,
    active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(CourseEquivalence)
    if career_id:
        query = query.filter_by(career_id=career_id)
    if version:
        query = query.filter_by(curriculum_version=version)
    if active is not None:
        query = query.filter_by(active=active)
    return [
        output(db, item)
        for item in query.order_by(CourseEquivalence.course_equivalence_id)
        .offset(skip)
        .limit(limit)
    ]


@router.get("/equivalences/context/{career_id}")
def context(career_id: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    career = db.get(Career, career_id)
    if not career:
        raise HTTPException(404, "Carrera no encontrada")
    courses = (
        db.query(CurriculumCourse)
        .filter_by(career_id=career_id)
        .order_by(CurriculumCourse.term_number)
        .all()
    )
    return {
        "active_version": career.curriculum_version,
        "versions": sorted({c.curriculum_version for c in courses}),
        "courses": [
            {
                "subject_id": c.subject_id,
                "code": c.subject.code,
                "name": c.subject.description,
                "version": c.curriculum_version,
                "credits": c.credits,
            }
            for c in courses
        ],
    }


@router.post("/equivalences/preview")
def preview(data: EquivalenceCreate, db: Session = Depends(get_db), user: User = Depends(manager)):
    validate(db, data)
    candidate = SimpleNamespace(**data.model_dump(exclude={"reason"}), course_equivalence_id=0)
    return impact(db, candidate)


@router.post("/equivalences", response_model=EquivalenceOut)
def create(data: EquivalenceCreate, db: Session = Depends(get_db), user: User = Depends(manager)):
    validate(db, data)
    item = CourseEquivalence(
        **data.model_dump(exclude={"reason"}),
        created_by=user.user_id,
        updated_by=user.user_id,
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(item)
    db.flush()
    audit_event(
        db,
        user.user_id,
        "equivalence.created",
        f"equivalence:{item.course_equivalence_id}",
        f"{data.source_subject_id} → {data.target_subject_id}; carrera {data.career_id}; versión {data.curriculum_version}; activa={data.active}; {data.reason}",
    )
    db.commit()
    return output(db, item)


@router.get("/equivalences/{identifier}/impact")
def rule_impact(
    identifier: int, active: bool, db: Session = Depends(get_db), user: User = Depends(manager)
):
    item = get_rule(db, identifier)
    candidate = SimpleNamespace(
        **{
            k: getattr(item, k)
            for k in EquivalenceCreate.model_fields
            if k not in {"reason", "active"}
        },
        active=active,
        course_equivalence_id=item.course_equivalence_id,
    )
    if active and not item.active:
        validate(
            db,
            EquivalenceCreate(
                career_id=item.career_id,
                source_subject_id=item.source_subject_id,
                target_subject_id=item.target_subject_id,
                curriculum_version=item.curriculum_version,
                active=True,
            ),
            item.course_equivalence_id,
        )
    return impact(db, candidate, item.course_equivalence_id)


@router.patch("/equivalences/{identifier}", response_model=EquivalenceOut)
def edit(
    identifier: int,
    data: EquivalenceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(manager),
):
    item = get_rule(db, identifier)
    if data.active and not item.active:
        validate(
            db,
            EquivalenceCreate(
                career_id=item.career_id,
                source_subject_id=item.source_subject_id,
                target_subject_id=item.target_subject_id,
                curriculum_version=item.curriculum_version,
                active=True,
            ),
            item.course_equivalence_id,
        )
    before = item.active
    item.active, item.notes = data.active, data.notes
    item.updated_by, item.updated_at = user.user_id, datetime.now(UTC).replace(tzinfo=None)
    action = (
        "equivalence.updated"
        if before == data.active
        else "equivalence.activated"
        if data.active
        else "equivalence.deactivated"
    )
    audit_event(
        db,
        user.user_id,
        action,
        f"equivalence:{identifier}",
        f"activa {before} → {data.active}; {data.reason}; observaciones: {data.notes}",
    )
    db.commit()
    return output(db, item)


@router.get("/equivalences/{identifier}/history")
def history(identifier: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    get_rule(db, identifier)
    return [
        {
            "audit_log_id": a.audit_log_id,
            "action": a.action,
            "detail": a.detail,
            "created_at": a.created_at,
            "actor": db.get(User, a.user_id).username
            if a.user_id and db.get(User, a.user_id)
            else "Usuario no disponible",
        }
        for a in db.query(AuditLog)
        .filter_by(resource=f"equivalence:{identifier}")
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
    ]
