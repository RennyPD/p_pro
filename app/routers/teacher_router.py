from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from app.auth import ensure_teacher_access, get_current_user, is_admin, require_permissions
from app.db.Session import get_db
from app.models.configuration_model import AcademicPeriod
from app.models.scheduling_model import SectionMeeting
from app.models.section_model import Section
from app.models.teacher_model import Teacher
from app.models.user_model import User
from app.pagination import paginate_and_filter
from app.schemas.teacher_schema import (
    TeacherCreate,
    TeacherMeeting,
    TeacherOut,
    TeacherSectionLoad,
    TeacherUpdate,
    TeacherWorkload,
)
from app.services.teacher_service import (
    create_teacher_service,
    delete_teacher_service,
    get_teacher_by_id_service,
    update_teacher_service,
)

router = APIRouter(prefix="/teachers", tags=["teachers"])
teacher_manager = require_permissions("academic.manage", fallback_roles=("admin",))


@router.post("/", response_model=TeacherOut, dependencies=[Depends(teacher_manager)])
def create_teacher(teacher_data: TeacherCreate, db: Session = Depends(get_db)):
    return create_teacher_service(db, teacher_data)


@router.get("/", response_model=list[TeacherOut], dependencies=[Depends(get_current_user)])
def get_teachers(
    q: str | None = None,
    department: str | None = None,
    active: bool | None = None,
    employment_type: str | None = Query(None, pattern="^(full_time|part_time|adjunct|substitute)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Teacher).options(selectinload(Teacher.sections))
    if department:
        query = query.filter(Teacher.department == department)
    if active is not None:
        query = query.filter(Teacher.active == active)
    if employment_type:
        query = query.filter(Teacher.employment_type == employment_type)
    if not is_admin(user):
        if user.teacher_id is None:
            return []
        query = query.filter(Teacher.teacher_id == user.teacher_id)
    return paginate_and_filter(
        query.order_by(Teacher.last_name, Teacher.first_name).all(),
        skip,
        limit,
        q,
        ("full_name", "email", "specialty", "department", "employee_code", "document_number"),
    )


@router.get("/departments", response_model=list[str])
def teacher_departments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Teacher.department).filter(
        Teacher.department.isnot(None), Teacher.department != ""
    )
    if not is_admin(user):
        if user.teacher_id is None:
            return []
        query = query.filter(Teacher.teacher_id == user.teacher_id)
    return [row[0] for row in query.distinct().order_by(Teacher.department).all()]


@router.get("/{teacher_id}/workload", response_model=TeacherWorkload)
def teacher_workload(
    teacher_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_teacher_access(user, teacher_id)
    teacher = get_teacher_by_id_service(db, teacher_id)
    sections = (
        db.query(Section)
        .options(selectinload(Section.enrollments), selectinload(Section.subject))
        .filter(Section.teacher_id == teacher.teacher_id)
        .all()
    )
    periods = sorted(
        {section.period_name for section in sections if section.period_name}, reverse=True
    )
    current = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if current and current.name not in periods:
        periods.insert(0, current.name)
    selected_period = (
        period
        if period is not None
        else current.name
        if current
        else periods[0]
        if periods
        else None
    )
    meetings_by_section = {}
    for meeting in (
        db.query(SectionMeeting)
        .join(Section)
        .options(selectinload(SectionMeeting.classroom))
        .filter(Section.teacher_id == teacher_id)
        .order_by(SectionMeeting.day_of_week, SectionMeeting.start_time)
        .all()
    ):
        meetings_by_section.setdefault(meeting.section_id, []).append(meeting)
    rows = []
    unique_students = set()
    hours = 0.0
    active_sections = 0
    for section in sections:
        if selected_period and section.period_name != selected_period:
            continue
        days = [day.strip() for day in section.days_of_week.split(",") if day.strip()]
        start = section.start_time.hour * 60 + section.start_time.minute
        end = section.end_time.hour * 60 + section.end_time.minute
        weekly_hours = round((end - start) / 60 * len(set(days)), 2)
        meetings = meetings_by_section.get(section.section_id, [])
        day_order = {
            day: index
            for index, day in enumerate(
                ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
            )
        }
        meetings.sort(
            key=lambda meeting: (day_order.get(meeting.day_of_week, 7), meeting.start_time)
        )
        if meetings:
            weekly_hours = round(
                sum(
                    (
                        meeting.end_time.hour * 60
                        + meeting.end_time.minute
                        - meeting.start_time.hour * 60
                        - meeting.start_time.minute
                    )
                    / 60
                    for meeting in meetings
                ),
                2,
            )
        enrolled = [
            item
            for item in section.enrollments
            if item.state == "enrolled"
            and (not section.period_name or item.period == section.period_name)
        ]
        if section.status not in {"closed", "cancelled"}:
            active_sections += 1
            hours += weekly_hours
            unique_students.update(item.student_id for item in enrolled)
        rows.append(
            TeacherSectionLoad(
                section_id=section.section_id,
                section_code=section.code,
                subject_code=section.subject.code,
                subject_name=section.subject.description,
                period=section.period_name,
                status=section.status,
                modality=section.modality,
                room=section.room,
                days_of_week=days,
                start_time=section.start_time.strftime("%H:%M"),
                end_time=section.end_time.strftime("%H:%M"),
                capacity=section.capacity,
                enrolled_students=len(enrolled),
                scheduled_weekly_hours=weekly_hours,
                meetings=[
                    TeacherMeeting(
                        day=meeting.day_of_week,
                        start_time=meeting.start_time.strftime("%H:%M"),
                        end_time=meeting.end_time.strftime("%H:%M"),
                        room=meeting.classroom.name if meeting.classroom else section.room,
                        modality=meeting.modality,
                    )
                    for meeting in meetings
                ],
            )
        )
    return TeacherWorkload(
        teacher_id=teacher_id,
        selected_period=selected_period,
        periods=periods,
        active_sections=active_sections,
        unique_students=len(unique_students),
        scheduled_weekly_hours=round(hours, 2),
        sections=rows,
    )


@router.get("/{teacher_id}", response_model=TeacherOut, dependencies=[Depends(get_current_user)])
def get_teacher_by_id(
    teacher_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):

    ensure_teacher_access(user, teacher_id)
    return get_teacher_by_id_service(db, teacher_id)


@router.patch("/{teacher_id}", response_model=TeacherOut, dependencies=[Depends(teacher_manager)])
def update_teacher(teacher_id: int, teacher_data: TeacherUpdate, db: Session = Depends(get_db)):
    return update_teacher_service(db, teacher_id, teacher_data)


@router.delete("/{teacher_id}", dependencies=[Depends(teacher_manager)])
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    return delete_teacher_service(db, teacher_id)
