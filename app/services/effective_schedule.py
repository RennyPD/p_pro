from fastapi import HTTPException
from sqlalchemy.orm import selectinload

from app.enums.dayEnum import DAY_ORDER, canonical_day
from app.models.configuration_model import AcademicPeriod
from app.models.scheduling_model import SectionMeeting
from app.models.section_model import Section
from app.schemas.scheduling_schema import ScheduleBlock


def load_schedule():
    return selectinload(Section.meetings).joinedload(SectionMeeting.classroom)


def legacy_blocks(section: Section) -> list[ScheduleBlock]:
    days = {day for value in section.days_of_week.split(",") if (day := canonical_day(value))}
    return [
        ScheduleBlock(
            day_of_week=day,
            start_time=section.start_time,
            end_time=section.end_time,
            room=section.room,
            modality=section.modality,
        )
        for day in sorted(days, key=DAY_ORDER.__getitem__)
    ]


def meeting_block(meeting: SectionMeeting) -> ScheduleBlock | None:
    day = canonical_day(meeting.day_of_week)
    if day is None:
        return None
    return ScheduleBlock(
        day_of_week=day,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        room=meeting.classroom.name if meeting.classroom else meeting.section.room,
        classroom_id=meeting.classroom_id,
        modality=meeting.modality,
        virtual_url=meeting.virtual_url,
    )


def effective_blocks(section: Section) -> list[ScheduleBlock]:
    if not section.meetings:
        return legacy_blocks(section)
    blocks = [block for item in section.meetings if (block := meeting_block(item)) is not None]
    return sorted(blocks, key=lambda block: (DAY_ORDER[block.day_of_week], block.start_time))


def overlap(first: ScheduleBlock, second: ScheduleBlock) -> bool:
    return (
        first.day_of_week == second.day_of_week
        and first.start_time < second.end_time
        and second.start_time < first.end_time
    )


def schedule_periods(section, active: str | None) -> set[str]:
    if section.period_name:
        return {section.period_name}
    enrolled = {item.period for item in section.enrollments if item.state == "enrolled"}
    return enrolled or {active or ""}


def overlapping_periods(first, second, by_name):
    p, q = by_name.get(first), by_name.get(second)
    if (p and p.status == "closed") or (q and q.status == "closed"):
        return False
    if first == second:
        return True
    return bool(p and q and p.start_date <= q.end_date and q.start_date <= p.end_date)


def same_room(first, second):
    if first.classroom_id and second.classroom_id:
        return first.classroom_id == second.classroom_id
    a, b = first.room.strip().casefold(), second.room.strip().casefold()
    return bool(
        a
        and a == b
        and a != "por asignar"
        and first.modality != "virtual"
        and second.modality != "virtual"
    )


def validate_schedule(db, section, blocks):
    for index, block in enumerate(blocks):
        if any(overlap(block, other) for other in blocks[index + 1 :]):
            raise HTTPException(409, f"Hay dos bloques superpuestos en la sección {section.code}")

    if section.status in {"closed", "cancelled"}:
        return
    periods = db.query(AcademicPeriod).all()
    by_name = {period.name: period for period in periods}
    active = next(
        (period.name for period in periods if period.active and period.status != "closed"), None
    )
    when = schedule_periods(section, active)
    students = {item.student_id for item in section.enrollments if item.state == "enrolled"}
    candidates = (
        db.query(Section)
        .options(load_schedule(), selectinload(Section.enrollments))
        .filter(
            Section.section_id != section.section_id,
            Section.status.in_(("published", "active")),
        )
    )
    for other in candidates:
        simultaneous = any(
            overlapping_periods(name, other_name, by_name)
            for name in when
            for other_name in schedule_periods(other, active)
        )
        if not simultaneous:
            continue
        same_teacher = section.teacher_id == other.teacher_id
        same_students = any(
            item.student_id in students and item.state == "enrolled" for item in other.enrollments
        )
        existing_blocks = effective_blocks(other)
        for block in blocks:
            for existing in existing_blocks:
                if not overlap(block, existing):
                    continue
                resource = (
                    "docente"
                    if same_teacher
                    else "aula"
                    if same_room(block, existing)
                    else "estudiantes inscritos"
                    if same_students
                    else None
                )
                if resource:
                    raise HTTPException(
                        409,
                        f"El bloque del {block.day_of_week} de {section.code} se superpone con "
                        f"{other.code} por {resource}. Cambia el horario o la asignación",
                    )


ROOM_UNASSIGNED = {"", "por asignar"}


def room_conflict(db, section, blocks):
    """First other open section (drafts included) holding the same room at an overlapping time.

    Drafts count because a planned section already reserves its room; closed and
    cancelled sections never do. Returns (other_section, block, existing_block) or None.
    """
    periods = db.query(AcademicPeriod).all()
    by_name = {period.name: period for period in periods}
    active = next(
        (period.name for period in periods if period.active and period.status != "closed"), None
    )
    when = schedule_periods(section, active)
    candidates = (
        db.query(Section)
        .options(load_schedule(), selectinload(Section.enrollments))
        .filter(Section.status.notin_(("closed", "cancelled")))
    )
    if section.section_id is not None:
        candidates = candidates.filter(Section.section_id != section.section_id)
    for other in candidates:
        if not any(
            overlapping_periods(name, other_name, by_name)
            for name in when
            for other_name in schedule_periods(other, active)
        ):
            continue
        for block in blocks:
            for existing in effective_blocks(other):
                if overlap(block, existing) and same_room(block, existing):
                    return other, block, existing
    return None
