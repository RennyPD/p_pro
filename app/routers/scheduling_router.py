from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ensure_section_access, get_current_user, require_permissions
from app.db.Session import get_db
from app.models.scheduling_model import Classroom, SectionMeeting
from app.models.section_model import Section
from app.models.user_model import User
from app.schemas.scheduling_schema import (
    ClassroomCreate,
    ClassroomOut,
    MeetingCreate,
    MeetingOut,
)

router = APIRouter(prefix="/scheduling", tags=["scheduling"])
scheduling_manager = require_permissions("academic.manage", fallback_roles=("admin", "teacher"))


def meeting_out(meeting: SectionMeeting) -> MeetingOut:
    return MeetingOut(
        meeting_id=meeting.meeting_id,
        section_id=meeting.section_id,
        classroom_id=meeting.classroom_id,
        classroom_name=meeting.classroom.name if meeting.classroom else None,
        day_of_week=meeting.day_of_week,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        modality=meeting.modality,
        virtual_url=meeting.virtual_url,
    )


@router.get("/classrooms", response_model=list[ClassroomOut])
def list_classrooms(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(Classroom).order_by(Classroom.name).all()


@router.post("/classrooms", response_model=ClassroomOut, dependencies=[Depends(scheduling_manager)])
def create_classroom(data: ClassroomCreate, db: Session = Depends(get_db)):
    room = Classroom(**data.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/sections/{section_id}/meetings", response_model=list[MeetingOut])
def list_meetings(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id, allow_student=True)
    meetings = (
        db.query(SectionMeeting)
        .filter(SectionMeeting.section_id == section_id)
        .order_by(SectionMeeting.day_of_week, SectionMeeting.start_time)
        .all()
    )
    return [meeting_out(item) for item in meetings]


@router.post("/meetings", response_model=MeetingOut)
def create_meeting(
    data: MeetingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(scheduling_manager),
):
    section = ensure_section_access(db, user, data.section_id)
    if data.classroom_id is not None:
        room = db.get(Classroom, data.classroom_id)
        if room is None or not room.active:
            raise HTTPException(status_code=422, detail="Classroom is not available")
        if room.capacity < section.capacity:
            raise HTTPException(
                status_code=409, detail="Classroom capacity is below section capacity"
            )
    conflicts = (
        db.query(SectionMeeting)
        .join(Section, SectionMeeting.section_id == Section.section_id)
        .filter(
            SectionMeeting.day_of_week == data.day_of_week,
            SectionMeeting.start_time < data.end_time,
            SectionMeeting.end_time > data.start_time,
        )
        .all()
    )
    for conflict in conflicts:
        same_teacher = conflict.section.teacher_id == section.teacher_id
        same_room = data.classroom_id is not None and conflict.classroom_id == data.classroom_id
        if same_teacher or same_room:
            resource = "teacher" if same_teacher else "classroom"
            raise HTTPException(status_code=409, detail=f"Schedule conflict for {resource}")
    meeting = SectionMeeting(**data.model_dump())
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting_out(meeting)


@router.delete("/meetings/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(scheduling_manager),
):
    meeting = db.get(SectionMeeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    ensure_section_access(db, user, meeting.section_id)
    db.delete(meeting)
    db.commit()
    return {"message": "Meeting deleted successfully"}
