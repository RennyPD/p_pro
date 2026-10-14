import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
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
from app.models.community_model import Announcement, Guardian, Notification, StudentGuardian
from app.models.enrollment_model import Enrollment
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.schemas.community_schema import (
    AnnouncementCreate,
    AnnouncementOut,
    GuardianCreate,
    GuardianLinkCreate,
    GuardianLinkOut,
    NotificationOut,
)
from app.services.governance_workflow import lock_governance, record

router = APIRouter(prefix="/community", tags=["community"])


def link_out(link: StudentGuardian) -> GuardianLinkOut:
    return GuardianLinkOut(
        student_guardian_id=link.student_guardian_id,
        student_id=link.student_id,
        guardian_id=link.guardian_id,
        relationship=link.relationship,
        primary_contact=link.primary_contact,
        emergency_contact=link.emergency_contact,
        authorized_pickup=link.authorized_pickup,
        guardian_name=f"{link.guardian.first_name} {link.guardian.last_name}",
        guardian_email=link.guardian.email,
    )


@router.post("/guardians", dependencies=[Depends(require_roles("admin"))])
def create_guardian(data: GuardianCreate, db: Session = Depends(get_db)):
    guardian = Guardian(**data.model_dump())
    db.add(guardian)
    db.commit()
    db.refresh(guardian)
    return guardian


@router.post(
    "/guardian-links",
    response_model=GuardianLinkOut,
    dependencies=[Depends(require_roles("admin"))],
)
def link_guardian(data: GuardianLinkCreate, db: Session = Depends(get_db)):
    link = StudentGuardian(**data.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link_out(link)


@router.get("/students/{student_id}/guardians", response_model=list[GuardianLinkOut])
def student_guardians(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ensure_student_academic_access(db, user, student_id)
    return [
        link_out(item)
        for item in db.query(StudentGuardian).filter(StudentGuardian.student_id == student_id).all()
    ]


communications_manager = require_permissions(
    "communications.manage", fallback_roles=("admin", "teacher")
)


def target_users(db, data, user):
    if data.audience in {"section", "section_guardians"}:
        section = ensure_section_access(db, user, data.section_id or 0)
        if section.status in {"closed", "cancelled"}:
            raise HTTPException(
                409, "La sección está cerrada o cancelada para nuevas comunicaciones"
            )
        students = (
            db.query(Enrollment.student_id)
            .join(Student)
            .filter(
                Enrollment.section_id == section.section_id,
                Enrollment.state == "enrolled",
                Student.active.is_(True),
            )
        )
        if section.period_name:
            students = students.filter(Enrollment.period == section.period_name)
        if data.audience == "section":
            return db.query(User).filter(User.student_id.in_(students)).all()
        guardians = db.query(StudentGuardian.guardian_id).filter(
            StudentGuardian.student_id.in_(students)
        )
        return db.query(User).filter(User.guardian_id.in_(guardians)).distinct().all()
    if not is_admin(user):
        raise HTTPException(403, "El docente solo puede comunicar a sus secciones o sus tutores")
    query = db.query(User).join(User.role)
    if data.audience != "all":
        query = query.filter(User.role.has(name=data.audience))
    # Exclude inactive linked student/teacher profiles; users have no standalone active flag.
    return [
        u
        for u in query.all()
        if (not u.student_id or (s := db.get(Student, u.student_id)) and s.active)
        and (not u.teacher_id or (t := db.get(Teacher, u.teacher_id)) and t.active)
        and (
            not u.guardian_id
            or db.query(StudentGuardian)
            .join(Student)
            .filter(StudentGuardian.guardian_id == u.guardian_id, Student.active.is_(True))
            .first()
        )
    ]


def fingerprint(targets):
    return hashlib.sha256(
        ",".join(str(u.user_id) for u in sorted(targets, key=lambda u: u.user_id)).encode()
    ).hexdigest()


def announcement_out(db, item):
    values = {
        k: getattr(item, k)
        for k in (
            "announcement_id",
            "title",
            "body",
            "audience",
            "section_id",
            "created_by",
            "published_at",
        )
    }
    section = db.get(Section, item.section_id) if item.section_id else None
    linked = db.query(Notification).filter_by(announcement_id=item.announcement_id).all()
    # Legacy deliveries cannot be inferred safely from coincident titles.
    return AnnouncementOut(
        **values,
        section_name=f"{section.code} · {section.subject.description}" if section else None,
        author_name=db.get(User, item.created_by).username,
        delivery_count=len(linked) if item.delivery_key or linked else None,
        read_count=sum(n.read_at is not None for n in linked)
        if item.delivery_key or linked
        else None,
    )


@router.get("/sections")
def communication_sections(
    db: Session = Depends(get_db), user: User = Depends(communications_manager)
):
    query = db.query(Section).filter(Section.status.in_(("published", "active")))
    if not is_admin(user):
        query = (
            query.filter(Section.teacher_id == user.teacher_id)
            if user.teacher_id
            else query.filter(False)
        )
    return [
        {
            "section_id": s.section_id,
            "label": f"{s.code} · {s.subject.description} · {s.period_name or 'Sin período asignado'}",
        }
        for s in query.order_by(Section.code)
    ]


@router.post("/announcements/preview")
def preview_announcement(
    data: AnnouncementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(communications_manager),
):
    targets = target_users(db, data, user)
    return {
        "count": len(targets),
        "fingerprint": fingerprint(targets),
        "roles": {
            role: sum(u.role.name == role for u in targets)
            for role in ("admin", "teacher", "student", "guardian")
        },
    }


@router.post("/announcements", response_model=AnnouncementOut)
def create_announcement(
    data: AnnouncementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(communications_manager),
):
    lock_governance(db)
    if data.delivery_key:
        existing = db.query(Announcement).filter_by(delivery_key=data.delivery_key).first()
        if existing:
            if existing.created_by != user.user_id or any(
                getattr(existing, k) != getattr(data, k)
                for k in ("title", "body", "audience", "section_id")
            ):
                raise HTTPException(409, "La clave de publicación pertenece a otro aviso")
            db.rollback()
            return announcement_out(db, existing)
    targets = target_users(db, data, user)
    if not targets:
        raise HTTPException(409, "No hay destinatarios elegibles; no se publicó el aviso")
    if data.expected_recipients and data.expected_recipients != fingerprint(targets):
        raise HTTPException(409, "Los destinatarios cambiaron; vuelve a revisar el alcance")
    item = Announcement(**data.model_dump(exclude={"expected_recipients"}), created_by=user.user_id)
    db.add(item)
    db.flush()
    for target in targets:
        db.add(
            Notification(
                user_id=target.user_id,
                title=data.title,
                body=data.body,
                category="announcement",
                announcement_id=item.announcement_id,
            )
        )
    record(
        db,
        user,
        "announcement.published",
        f"announcement:{item.announcement_id}",
        f"Audiencia {data.audience}; sección {data.section_id}; destinatarios {len(targets)}",
    )
    db.commit()
    return announcement_out(db, item)


@router.get("/announcements", response_model=list[AnnouncementOut])
def announcements(db: Session = Depends(get_db), user: User = Depends(communications_manager)):
    query = db.query(Announcement)
    if not is_admin(user):
        query = query.filter(Announcement.created_by == user.user_id)
    return [
        announcement_out(db, a)
        for a in query.order_by(
            Announcement.published_at.desc(), Announcement.announcement_id.desc()
        )
    ]


@router.post("/notifications/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.user_id, Notification.read_at.is_(None))
        .update(
            {Notification.read_at: datetime.now(UTC).replace(tzinfo=None)},
            synchronize_session=False,
        )
    )
    db.commit()
    return {"marked": count}


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def read_notification(
    notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    item = db.get(Notification, notification_id)
    if item is None or item.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    if item.read_at is None:
        item.read_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(item)
    return item
