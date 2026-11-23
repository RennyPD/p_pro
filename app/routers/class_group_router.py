"""Fixed school groups (Fase 3, block C): groups, members, subjects, promotion."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.class_group_model import ClassGroup
from app.models.student_model import Student
from app.pagination import page_query, search
from app.schemas.class_group_schema import (
    ClassGroupCreate,
    ClassGroupDetail,
    ClassGroupOut,
    ClassGroupUpdate,
    MemberAdd,
    MemberChange,
    MemberTransfer,
    PromotionProposal,
    RecoveryIn,
    ReinscriptionIn,
    ReinscriptionOut,
    ResultConfirmation,
    SubjectsGenerated,
    SubjectTeacherIn,
)
from app.services import class_groups as service
from app.services.governance_workflow import history, lock_governance, record

router = APIRouter(tags=["class groups"])
group_manager = require_permissions("sections.manage")
member_manager = require_permissions("enrollments.manage")
grade_manager = require_permissions("grades.manage")


def group_out(group: ClassGroup) -> dict:
    teacher = group.homeroom_teacher
    return {
        "class_group_id": group.class_group_id,
        "career_id": group.career_id,
        "grade_number": group.grade_number,
        "name": group.name,
        "school_year_id": group.school_year_id,
        "homeroom_teacher_id": group.homeroom_teacher_id,
        "room": group.room,
        "capacity": group.capacity,
        "status": group.status,
        "label": group.label,
        "career_name": group.career.name,
        "school_year_name": group.school_year.name,
        "homeroom_teacher_name": f"{teacher.first_name} {teacher.last_name}" if teacher else None,
        "member_count": len(service.active_members(group)),
    }


def detail_out(db: Session, group: ClassGroup) -> dict:
    sections = service.group_sections(db, group)
    subjects = []
    for course in service.curriculum(db, group):
        teacher_id = service.teacher_for(group, course.subject_id)
        teacher = db.get(service.Teacher, teacher_id) if teacher_id else None
        subjects.append(
            {
                "subject_id": course.subject_id,
                "code": course.subject.code,
                "name": course.subject.description,
                "teacher_id": teacher_id,
                "teacher_name": f"{teacher.first_name} {teacher.last_name}" if teacher else None,
                "sections": sum(1 for s in sections if s.subject_id == course.subject_id),
            }
        )
    members = [
        {
            "member_id": m.member_id,
            "student_id": m.student_id,
            "student_name": m.student.full_name,
            "enrollment_number": m.student.enrollment_number,
            "status": m.status,
            "joined_on": m.joined_on,
            "left_on": m.left_on,
            "result": m.result,
            "result_confirmed_at": m.result_confirmed_at,
            "result_note": m.result_note,
            "financial_hold": m.student.financial_hold,
            "academic_hold": m.student.academic_hold,
        }
        for m in sorted(group.members, key=lambda m: (m.status != "enrolled", m.student.last_name))
    ]
    return group_out(group) | {
        "members": members,
        "subjects": subjects,
        "open_periods": [p.name for p in service.open_periods(db, group)],
    }


@router.get("/class-groups/", response_model=list[ClassGroupOut])
def list_class_groups(
    response: Response,
    q: str | None = None,
    school_year_id: int | None = None,
    career_id: int | None = None,
    grade_number: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = search(service.visible_groups(db, user), q, ClassGroup.name)
    for column, value in (
        (ClassGroup.school_year_id, school_year_id),
        (ClassGroup.career_id, career_id),
        (ClassGroup.grade_number, grade_number),
    ):
        if value is not None:
            query = query.filter(column == value)
    query = query.order_by(
        ClassGroup.school_year_id.desc(),
        ClassGroup.career_id,
        ClassGroup.grade_number,
        ClassGroup.name,
    )
    return [group_out(group) for group in page_query(query, response, skip, limit)]


@router.post("/class-groups/", response_model=ClassGroupOut)
def create_class_group(
    data: ClassGroupCreate, db: Session = Depends(get_db), user=Depends(group_manager)
):
    lock_governance(db)
    service.validate_group(db, data.career_id, data.grade_number, data.school_year_id)
    service.validate_teacher(db, data.homeroom_teacher_id)
    service.ensure_unique_group(db, data.model_dump())
    group = ClassGroup(**data.model_dump(), status="active")
    db.add(group)
    db.flush()
    record(
        db,
        user,
        "class_group.created",
        f"class-group:{group.class_group_id}",
        f"Creación: {group.label}; año {group.school_year.name}; cupo {group.capacity}",
    )
    db.commit()
    return group_out(group)


@router.get("/class-groups/{class_group_id}", response_model=ClassGroupDetail)
def get_class_group(
    class_group_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return detail_out(db, service.ensure_group_access(db, user, class_group_id))


@router.patch("/class-groups/{class_group_id}", response_model=ClassGroupDetail)
def update_class_group(
    class_group_id: int,
    data: ClassGroupUpdate,
    db: Session = Depends(get_db),
    user=Depends(group_manager),
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    values = data.model_dump(exclude_unset=True)
    if "name" in values:
        values["name"] = (values["name"] or "").strip().upper()
        if not values["name"]:
            raise HTTPException(422, "El grupo necesita un nombre")
        service.ensure_unique_group(
            db,
            {
                "career_id": group.career_id,
                "grade_number": group.grade_number,
                "name": values["name"],
                "school_year_id": group.school_year_id,
            },
            group,
        )
    if "homeroom_teacher_id" in values:
        service.validate_teacher(db, values["homeroom_teacher_id"])
    if values.get("capacity") is not None and values["capacity"] < len(
        service.active_members(group)
    ):
        raise HTTPException(409, "El cupo no puede ser menor que los estudiantes del grupo")
    for key, value in values.items():
        if value is None and key != "homeroom_teacher_id":
            continue
        if getattr(group, key) != value:
            record(
                db,
                user,
                "class_group.updated",
                f"class-group:{class_group_id}",
                f"{key}: {getattr(group, key)} → {value}",
            )
            setattr(group, key, value)
    db.commit()
    return detail_out(db, group)


@router.delete("/class-groups/{class_group_id}")
def delete_class_group(
    class_group_id: int, db: Session = Depends(get_db), user=Depends(group_manager)
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    if group.members or service.group_sections(db, group):
        raise HTTPException(409, "Solo se elimina un grupo sin estudiantes ni materias")
    record(db, user, "class_group.deleted", f"class-group:{class_group_id}", group.label)
    db.delete(group)
    db.commit()
    return {"message": "Grupo eliminado"}


@router.get("/class-groups/{class_group_id}/history", dependencies=[Depends(member_manager)])
def class_group_history(class_group_id: int, db: Session = Depends(get_db)):
    return history(db, f"class-group:{class_group_id}")


@router.put("/class-groups/{class_group_id}/subjects/{subject_id}", response_model=ClassGroupDetail)
def set_subject_teacher(
    class_group_id: int,
    subject_id: int,
    data: SubjectTeacherIn,
    db: Session = Depends(get_db),
    user=Depends(group_manager),
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    moved = service.assign_subject_teacher(db, group, subject_id, data.teacher_id)
    record(
        db,
        user,
        "class_group.subject_teacher",
        f"class-group:{class_group_id}",
        f"Asignatura {subject_id}: docente {data.teacher_id}; {moved} secciones abiertas",
    )
    db.commit()
    return detail_out(db, group)


@router.post("/class-groups/{class_group_id}/generate-subjects", response_model=SubjectsGenerated)
def generate_group_subjects(
    class_group_id: int, db: Session = Depends(get_db), user=Depends(group_manager)
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    result = service.generate_subjects(db, group)
    record(
        db,
        user,
        "class_group.subjects_generated",
        f"class-group:{class_group_id}",
        f"{result['sections_created']} secciones; {result['enrollments_created']} inscripciones",
    )
    db.commit()
    return result


@router.post("/class-groups/{class_group_id}/members", response_model=ClassGroupDetail)
def add_group_member(
    class_group_id: int,
    data: MemberAdd,
    db: Session = Depends(get_db),
    user=Depends(member_manager),
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    student = db.get(Student, data.student_id)
    if student is None:
        raise HTTPException(404, "Estudiante no encontrado")
    service.add_member(db, group, student, user, data.override_reason)
    db.commit()
    return detail_out(db, group)


@router.post(
    "/class-groups/{class_group_id}/members/{member_id}/withdraw",
    response_model=ClassGroupDetail,
)
def withdraw_group_member(
    class_group_id: int,
    member_id: int,
    data: MemberChange,
    db: Session = Depends(get_db),
    user=Depends(member_manager),
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    service.withdraw_member(db, group, service.member_or_404(group, member_id), user, data.reason)
    db.commit()
    return detail_out(db, group)


@router.post(
    "/class-groups/{class_group_id}/members/{member_id}/transfer",
    response_model=ClassGroupDetail,
)
def transfer_group_member(
    class_group_id: int,
    member_id: int,
    data: MemberTransfer,
    db: Session = Depends(get_db),
    user=Depends(member_manager),
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    target = service.group_or_404(db, data.target_group_id)
    member = service.member_or_404(group, member_id)
    service.transfer_member(db, group, member, target, user, data.reason)
    db.commit()
    db.refresh(group)
    return detail_out(db, group)


@router.get(
    "/class-groups/{class_group_id}/promotion",
    response_model=PromotionProposal,
    dependencies=[Depends(member_manager)],
)
def promotion(class_group_id: int, db: Session = Depends(get_db)):
    return service.promotion_proposal(db, service.group_or_404(db, class_group_id))


@router.post("/class-groups/{class_group_id}/promotion", response_model=PromotionProposal)
def confirm_promotion(
    class_group_id: int,
    data: ResultConfirmation,
    db: Session = Depends(get_db),
    user=Depends(member_manager),
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    service.confirm_results(db, group, data.decisions, user)
    db.commit()
    return service.promotion_proposal(db, group)


@router.post(
    "/class-groups/{class_group_id}/members/{member_id}/recovery",
    response_model=PromotionProposal,
)
def record_recovery_exam(
    class_group_id: int,
    member_id: int,
    data: RecoveryIn,
    db: Session = Depends(get_db),
    user=Depends(grade_manager),
):
    """Completivo or extraordinario grade (Fase 3 D); teachers of the group or academic staff."""
    lock_governance(db)
    group = service.ensure_group_access(db, user, class_group_id)
    member = service.member_or_404(group, member_id)
    service.record_recovery(db, group, member, data.subject_id, data.kind, data.exam_grade, user)
    db.commit()
    return service.promotion_proposal(db, group)


@router.post("/class-groups/{class_group_id}/reinscribe", response_model=ReinscriptionOut)
def reinscribe_group(
    class_group_id: int,
    data: ReinscriptionIn,
    db: Session = Depends(get_db),
    user=Depends(member_manager),
):
    lock_governance(db)
    group = service.group_or_404(db, class_group_id)
    target = service.group_or_404(db, data.target_group_id)
    result = service.reinscribe(db, group, target, data.member_ids, user, data.override_reason)
    record(
        db,
        user,
        "class_group.reinscription",
        f"class-group:{class_group_id}",
        f"→ {target.label}: {len(result['reinscribed'])} reinscritos, "
        f"{len(result['blocked'])} pendientes",
    )
    db.commit()
    return result
