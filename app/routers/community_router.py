from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    ensure_section_access,
    ensure_student_academic_access,
    get_current_user,
    is_admin,
    require_roles,
)
from app.db.Session import get_db
from app.models.community_model import Announcement, Guardian, Notification, StudentGuardian
from app.models.enrollment_model import Enrollment
from app.models.user_model import User
from app.schemas.community_schema import (
    AnnouncementCreate,
    AnnouncementOut,
    GuardianCreate,
    GuardianLinkCreate,
    GuardianLinkOut,
    NotificationOut,
)

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


def target_users(db: Session, data: AnnouncementCreate) -> list[User]:
    if data.audience == "all":
        return db.query(User).all()
    if data.audience in {"admin", "teacher", "student"}:
        return db.query(User).join(User.role).filter_by(name=data.audience).all()
    student_ids = db.query(Enrollment.student_id).filter(Enrollment.section_id == data.section_id)
    return db.query(User).filter(User.student_id.in_(student_ids)).all()


@router.post("/announcements", response_model=AnnouncementOut)
def create_announcement(
    data: AnnouncementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    if data.audience == "section":
        ensure_section_access(db, user, data.section_id or 0)
    elif not is_admin(user):
        raise HTTPException(status_code=403, detail="Teachers can only announce to their sections")
    announcement = Announcement(**data.model_dump(), created_by=user.user_id)
    db.add(announcement)
    for target in target_users(db, data):
        db.add(
            Notification(
                user_id=target.user_id, title=data.title, body=data.body, category="announcement"
            )
        )
    db.commit()
    db.refresh(announcement)
    return announcement


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
    item.read_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(item)
    return item
