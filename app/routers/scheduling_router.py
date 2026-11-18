from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth import ensure_section_access, get_current_user, require_permissions, require_roles
from app.db.Session import get_db
from app.enums.dayEnum import DAY_ORDER, canonical_day
from app.models.scheduling_model import Classroom, SectionMeeting
from app.models.section_model import Section
from app.models.user_model import User
from app.pagination import page_query
from app.schemas.scheduling_schema import (
    ClassroomCreate,
    ClassroomOut,
    MeetingCreate,
    MeetingOut,
    ScheduleBlock,
)
from app.services.effective_schedule import legacy_blocks, meeting_block, validate_schedule
from app.services.governance_workflow import lock_governance, record

router = APIRouter(prefix="/scheduling", tags=["scheduling"])
scheduling_manager = require_roles("admin", "teacher")
classroom_manager = require_permissions("academic.manage", fallback_roles=("admin",))


def meeting_out(meeting: SectionMeeting) -> MeetingOut:
    return MeetingOut(
        meeting_id=meeting.meeting_id,
        section_id=meeting.section_id,
        classroom_id=meeting.classroom_id,
        classroom_name=meeting.classroom.name if meeting.classroom else None,
        day_of_week=canonical_day(meeting.day_of_week) or meeting.day_of_week,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        modality=meeting.modality,
        virtual_url=meeting.virtual_url,
    )


@router.get("/classrooms", response_model=list[ClassroomOut])
def list_classrooms(
    response: Response,
    q: str | None = None,
    active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = db.query(Classroom)
    if active is not None:
        query = query.filter(Classroom.active == active)
    if q and (term := q.strip()):
        query = query.filter(Classroom.name.icontains(term, autoescape=True))
    return page_query(query.order_by(Classroom.name, Classroom.classroom_id), response, skip, limit)


@router.post("/classrooms", response_model=ClassroomOut)
def create_classroom(
    data: ClassroomCreate, db: Session = Depends(get_db), user: User = Depends(classroom_manager)
):
    lock_governance(db)
    room = Classroom(**data.model_dump())
    db.add(room)
    db.flush()
    record(db, user, "classroom.created", f"classroom:{room.classroom_id}", "Alta de aula")
    db.commit()
    db.refresh(room)
    return room


def update_room(db, user, classroom_id, values):
    lock_governance(db)
    room = db.get(Classroom, classroom_id)
    if room is None:
        raise HTTPException(404, "No se encontró el aula solicitada")
    used_by = (
        db.query(Section)
        .join(Section.meetings)
        .filter(
            SectionMeeting.classroom_id == classroom_id,
            Section.status.in_(("published", "active")),
        )
        .all()
    )
    if any(
        not values.get("active", room.active)
        or values.get("capacity", room.capacity) < section.capacity
        for section in used_by
    ):
        raise HTTPException(409, f"El aula {room.name} tiene bloques activos. Reasígnalos primero")
    for key, value in values.items():
        setattr(room, key, value)
    action = "classroom.updated" if room.active else "classroom.retired"
    record(db, user, action, f"classroom:{classroom_id}", "Actualización administrativa de aula")
    db.commit()
    return room


@router.put("/classrooms/{classroom_id}", response_model=ClassroomOut)
def edit_classroom(
    classroom_id: int,
    data: ClassroomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(classroom_manager),
):
    return update_room(db, user, classroom_id, data.model_dump())


@router.delete("/classrooms/{classroom_id}", status_code=204)
def retire_classroom(
    classroom_id: int, db: Session = Depends(get_db), user: User = Depends(classroom_manager)
):
    update_room(db, user, classroom_id, {"active": False})


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
    return [
        meeting_out(item)
        for item in sorted(
            meetings,
            key=lambda item: (DAY_ORDER.get(canonical_day(item.day_of_week), 7), item.start_time),
        )
        if canonical_day(item.day_of_week)
    ]


def writable_section(db, user, section_id):
    section = ensure_section_access(db, user, section_id)
    if section.status in {"closed", "cancelled"}:
        raise HTTPException(409, f"La sección {section.code} conserva su horario histórico")
    return section


def save_meeting(db, user, data, existing=None):
    section = writable_section(db, user, data.section_id)
    room = None
    if data.classroom_id is not None:
        room = db.get(Classroom, data.classroom_id)
        if room is None or not room.active:
            raise HTTPException(422, "Selecciona un aula activa para el bloque")
        if room.capacity < section.capacity:
            raise HTTPException(
                409,
                f"El aula {room.name} no alcanza el cupo de {section.code}. Selecciona otra aula",
            )
    blocks = [
        block
        for item in section.meetings
        if item is not existing and (block := meeting_block(item)) is not None
    ]
    blocks.append(
        ScheduleBlock(
            **data.model_dump(exclude={"section_id"}),
            room=room.name if room else section.room,
        )
    )
    validate_schedule(db, section, blocks)
    meeting = existing if existing is not None else SectionMeeting()
    for key, value in data.model_dump().items():
        setattr(meeting, key, value)
    db.add(meeting)
    db.flush()
    action = "meeting.updated" if existing is not None else "meeting.created"
    record(db, user, action, f"meeting:{meeting.meeting_id}", f"Sección {section.code}")
    db.commit()
    db.refresh(meeting)
    return meeting_out(meeting)


@router.post("/meetings", response_model=MeetingOut)
def create_meeting(
    data: MeetingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(scheduling_manager),
):
    lock_governance(db)
    return save_meeting(db, user, data)


@router.put("/meetings/{meeting_id}", response_model=MeetingOut)
def update_meeting(
    meeting_id: int,
    data: MeetingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(scheduling_manager),
):
    lock_governance(db)
    meeting = db.get(SectionMeeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "No se encontró el bloque solicitado")
    writable_section(db, user, meeting.section_id)
    if meeting.section_id != data.section_id:
        raise HTTPException(409, "Crea otro bloque para cambiarlo de sección")
    return save_meeting(db, user, data, existing=meeting)


@router.delete("/meetings/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(scheduling_manager),
):
    lock_governance(db)
    meeting = db.get(SectionMeeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Reunión no encontrada")
    section = writable_section(db, user, meeting.section_id)
    remaining = [item for item in section.meetings if item is not meeting]
    blocks = [block for item in remaining if (block := meeting_block(item)) is not None]
    validate_schedule(db, section, blocks if remaining else legacy_blocks(section))
    db.delete(meeting)
    record(db, user, "meeting.deleted", f"meeting:{meeting_id}", f"Sección {section.code}")
    db.commit()
    return {"message": "Reunión eliminada"}
