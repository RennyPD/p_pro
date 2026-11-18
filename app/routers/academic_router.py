from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import (
    ACADEMIC_SCOPE,
    ensure_section_access,
    ensure_student_academic_access,
    ensure_teacher_access,
    get_current_user,
    has_scope,
)
from app.db.Session import get_db
from app.models.assessment_model import Assessment
from app.models.configuration_model import AcademicPeriod, InstitutionSettings
from app.models.curriculum_model import CurriculumCourse
from app.models.enrollment_model import CourseSelectionCart, Enrollment
from app.models.grade_model import Grade
from app.models.section_model import Section
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.academic_schema import (
    AttendanceCourseSummary,
    CartItemOut,
    CourseOffering,
    CourseSelectionSummary,
    GradeHistoryItem,
    RosterAttendanceItem,
    RosterGradeItem,
    ScheduleItem,
    SectionAcademicSummary,
    SectionRosterItem,
    SectionStudentItem,
    SectionWorkspace,
    StudentAcademicProfile,
    StudentEnrollmentSummary,
)
from app.schemas.enrollment_schema import EnrollmentCreate
from app.services.academic_grading import academic_result
from app.services.academic_recognition import current_courses, recognize
from app.services.business_time import business_date
from app.services.effective_schedule import effective_blocks, load_schedule
from app.services.enrollment_service import create_enrollment_service
from app.services.governance_workflow import lock_governance

router = APIRouter(prefix="/academic", tags=["academic queries"])


def schedule_item(section: Section) -> ScheduleItem:
    blocks = effective_blocks(section)
    first = blocks[0] if blocks else None
    return ScheduleItem(
        section_id=section.section_id,
        section_code=section.code,
        subject_code=section.subject.code,
        subject_name=section.subject.description,
        teacher_name=f"{section.teacher.first_name} {section.teacher.last_name}",
        room=first.room if first else section.room,
        modality=first.modality if first else section.modality,
        days_of_week=list(dict.fromkeys(block.day_of_week for block in blocks)),
        start_time=first.start_time if first else section.start_time,
        end_time=first.end_time if first else section.end_time,
        blocks=blocks,
    )


@router.get("/catalog", response_model=list[CourseOffering])
def course_catalog(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.student_id is None:
        raise HTTPException(
            status_code=403,
            detail="La selección de asignaturas solo está disponible para estudiantes",
        )
    student = db.get(Student, user.student_id)
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None:
        return []
    curriculum = {item.subject_id: item for item in current_courses(db, student)}
    recognition = recognize(db, student)
    current = {
        item.section_id: item.state
        for item in db.query(Enrollment)
        .filter(Enrollment.student_id == student.student_id, Enrollment.period == period.name)
        .all()
    }
    waitlist_positions = {
        item.section_id: item.waitlist_position
        for item in db.query(Enrollment)
        .filter(Enrollment.student_id == student.student_id, Enrollment.period == period.name)
        .all()
    }
    cart = {
        item.section_id: item
        for item in db.query(CourseSelectionCart)
        .filter(
            CourseSelectionCart.student_id == student.student_id,
            CourseSelectionCart.period == period.name,
        )
        .all()
    }
    selected_subjects = {
        item.section.subject_id: item.state
        for item in db.query(Enrollment)
        .filter(
            Enrollment.student_id == student.student_id,
            Enrollment.period == period.name,
            Enrollment.state.in_(("enrolled", "waitlisted")),
        )
        .all()
    }
    selected_subjects.update({item.section.subject_id: "cart" for item in cart.values()})
    results = []
    for section in (
        db.query(Section)
        .options(load_schedule())
        .filter(
            Section.subject_id.in_(list(curriculum)),
            Section.status.in_(("published", "active")),
            (Section.period_name == period.name) | (Section.period_name == ""),
        )
        .all()
    ):
        course = curriculum[section.subject_id]
        occupied = (
            db.query(Enrollment)
            .filter(
                Enrollment.section_id == section.section_id,
                Enrollment.period == period.name,
                Enrollment.state == "enrolled",
            )
            .count()
        )
        results.append(
            CourseOffering(
                **schedule_item(section).model_dump(),
                subject_id=section.subject_id,
                credits=course.credits,
                capacity=section.capacity,
                available_seats=max(section.capacity - occupied, 0),
                selection_status=current.get(section.section_id)
                or ("cart" if section.section_id in cart else None),
                waitlist_position=waitlist_positions.get(section.section_id),
                period=period.name,
                section_status=section.status,
                prerequisite_code=course.prerequisite.code if course.prerequisite else None,
                corequisite_code=course.corequisite.code if course.corequisite else None,
                selectable=section.subject_id not in selected_subjects
                and section.subject_id not in recognition.completed,
                restriction_reason=(
                    "Asignatura ya completada o reconocida por equivalencia"
                    if section.subject_id in recognition.completed
                    else "Ya seleccionaste esta asignatura"
                    if section.subject_id in selected_subjects
                    else None
                ),
            )
        )
    return results


@router.get("/catalog/summary", response_model=CourseSelectionSummary)
def course_selection_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.student_id is None:
        raise HTTPException(
            status_code=403,
            detail="La selección de asignaturas solo está disponible para estudiantes",
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    settings = db.get(InstitutionSettings, 1)
    maximum = settings.max_credits_per_period if settings else 24
    if period is None:
        return CourseSelectionSummary(
            period=None,
            period_status=None,
            selected_credits=0,
            maximum_credits=maximum,
            enrolled_sections=0,
            waitlisted_sections=0,
            cart_sections=0,
            cart_credits=0,
        )
    student = db.get(Student, user.student_id)
    enrollments = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == user.student_id,
            Enrollment.period == period.name,
            Enrollment.state.in_(("enrolled", "waitlisted")),
        )
        .all()
    )
    credits = {item.subject_id: item.credits for item in current_courses(db, student)}
    cart = (
        db.query(CourseSelectionCart)
        .filter_by(student_id=user.student_id, period=period.name)
        .all()
    )
    return CourseSelectionSummary(
        period=period.name,
        period_status=period.status,
        selected_credits=sum(
            item.curriculum_credits
            if item.curriculum_credits is not None
            else credits.get(item.section.subject_id, 0)
            for item in enrollments
        ),
        maximum_credits=maximum,
        enrolled_sections=sum(item.state == "enrolled" for item in enrollments),
        waitlisted_sections=sum(item.state == "waitlisted" for item in enrollments),
        cart_sections=len(cart),
        cart_credits=sum(credits.get(item.section.subject_id, 0) for item in cart),
    )


@router.get("/catalog/cart", response_model=list[CartItemOut])
def selection_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.student_id is None:
        raise HTTPException(
            status_code=403,
            detail="La selección de asignaturas solo está disponible para estudiantes",
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None:
        return []
    student = db.get(Student, user.student_id)
    credits = {item.subject_id: item.credits for item in current_courses(db, student)}
    items = (
        db.query(CourseSelectionCart)
        .filter_by(student_id=user.student_id, period=period.name)
        .all()
    )
    result = []
    for item in items:
        occupied = (
            db.query(Enrollment)
            .filter_by(section_id=item.section_id, period=period.name, state="enrolled")
            .count()
        )
        result.append(
            CartItemOut(
                cart_item_id=item.cart_item_id,
                section_id=item.section_id,
                section_code=item.section.code,
                subject_code=item.section.subject.code,
                subject_name=item.section.subject.description,
                credits=(
                    item.curriculum_credits
                    if item.curriculum_credits is not None
                    else credits.get(item.section.subject_id, 0)
                ),
                available_seats=max(item.section.capacity - occupied, 0),
                period=period.name,
            )
        )
    return result


@router.post("/catalog/cart/{section_id}")
def add_to_selection_cart(
    section_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    lock_governance(db)
    if user.student_id is None:
        raise HTTPException(
            status_code=403,
            detail="La selección de asignaturas solo está disponible para estudiantes",
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None or period.status not in {"registration", "active"}:
        raise HTTPException(
            status_code=409, detail="La selección de asignaturas está cerrada en este momento"
        )
    section = db.get(Section, section_id)
    student = db.get(Student, user.student_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Sección no encontrada")
    if (
        db.query(CurriculumCourse)
        .filter_by(
            career_id=student.career_id,
            subject_id=section.subject_id,
            curriculum_version=student.curriculum_version,
        )
        .first()
        is None
    ):
        raise HTTPException(
            status_code=409,
            detail="Esta asignatura no forma parte del plan de estudios del estudiante",
        )
    if section.subject_id in recognize(db, student).completed:
        raise HTTPException(
            status_code=409, detail="Asignatura ya completada o reconocida por equivalencia"
        )
    existing = (
        db.query(CourseSelectionCart)
        .join(Section)
        .filter(
            CourseSelectionCart.student_id == user.student_id,
            CourseSelectionCart.period == period.name,
            Section.subject_id == section.subject_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Esta asignatura ya está en la selección")
    item = CourseSelectionCart(
        student_id=user.student_id, section_id=section_id, period=period.name
    )
    db.add(item)
    db.commit()
    return {"cart_item_id": item.cart_item_id, "status": "cart"}


@router.delete("/catalog/cart/{section_id}")
def remove_from_selection_cart(
    section_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    lock_governance(db)
    item = (
        db.query(CourseSelectionCart)
        .filter_by(student_id=user.student_id, section_id=section_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Elemento de la selección no encontrado")
    db.delete(item)
    db.commit()
    return {"message": "Cart item removed"}


@router.post("/catalog/confirm")
def confirm_selection_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.student_id is None:
        raise HTTPException(
            status_code=403,
            detail="La selección de asignaturas solo está disponible para estudiantes",
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None:
        raise HTTPException(status_code=409, detail="No hay un período académico activo")
    items = (
        db.query(CourseSelectionCart)
        .filter_by(student_id=user.student_id, period=period.name)
        .order_by(CourseSelectionCart.created_at, CourseSelectionCart.cart_item_id)
        .all()
    )
    confirmed = []
    errors = []
    handled = set()
    for cart_item_id, section_id in [(item.cart_item_id, item.section_id) for item in items]:
        if cart_item_id in handled:
            continue
        section_ids = [section_id]
        try:
            lock_governance(db)
            item = db.get(CourseSelectionCart, cart_item_id)
            if item is None or item.student_id != user.student_id or item.section_id != section_id:
                db.rollback()
                continue
            active_period = db.query(AcademicPeriod).filter_by(active=True).first()
            if active_period is None or active_period.name != item.period:
                raise HTTPException(409, "Cambió el período vigente. Revisa tu selección")
            student = db.get(Student, user.student_id)
            requirements = {
                course.subject_id: course.corequisite_subject_id
                for course in current_courses(db, student)
            }
            subject = item.section.subject_id
            counterpart = requirements.get(subject)
            pair = None
            if counterpart is not None and requirements.get(counterpart) == subject:
                pair = (
                    db.query(CourseSelectionCart)
                    .join(CourseSelectionCart.section)
                    .filter(
                        CourseSelectionCart.student_id == student.student_id,
                        CourseSelectionCart.period == item.period,
                        Section.subject_id == counterpart,
                    )
                    .first()
                )
            batch = [item]
            if pair is not None:
                batch.append(pair)
                section_ids.append(pair.section_id)
                handled.add(pair.cart_item_id)
            results = []
            for queued in batch:
                enrollment = create_enrollment_service(
                    db,
                    EnrollmentCreate(
                        student_id=student.student_id,
                        section_id=queued.section_id,
                        period=queued.period,
                    ),
                    require_program=True,
                    paired_corequisite=counterpart if pair is not None and queued is item else None,
                    commit=False,
                )
                if pair is not None and enrollment.state != "enrolled":
                    raise HTTPException(
                        409, "Ambos correquisitos necesitan cupo para confirmarse juntos"
                    )
                results.append(
                    {
                        "section_id": queued.section_id,
                        "state": enrollment.state,
                        "waitlist_position": enrollment.waitlist_position,
                    }
                )
                db.delete(queued)
                db.flush()
            db.commit()
            confirmed.extend(results)
        except HTTPException as exc:
            db.rollback()
            errors.extend(
                {"section_id": identifier, "detail": exc.detail} for identifier in section_ids
            )
    return {"confirmed": confirmed, "errors": errors}


@router.post("/catalog/sections/{section_id}/select")
def select_course(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.student_id is None:
        raise HTTPException(
            status_code=403,
            detail="La selección de asignaturas solo está disponible para estudiantes",
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None or period.status not in {"registration", "active"}:
        raise HTTPException(
            status_code=409, detail="La selección de asignaturas está cerrada en este momento"
        )
    return create_enrollment_service(
        db,
        EnrollmentCreate(
            student_id=user.student_id,
            section_id=section_id,
            period=period.name,
        ),
        require_program=True,
    )


@router.post("/catalog/sections/{section_id}/withdraw")
def withdraw_course_selection(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.student_id is None:
        raise HTTPException(
            status_code=403,
            detail="La selección de asignaturas solo está disponible para estudiantes",
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == user.student_id,
            Enrollment.section_id == section_id,
            Enrollment.period == (period.name if period else ""),
            Enrollment.state.in_(("enrolled", "waitlisted", "withdrawn")),
        )
        .first()
    )
    if enrollment is None:
        raise HTTPException(status_code=404, detail="No se encontró una selección activa")
    from app.schemas.enrollment_schema import EnrollmentUpdate
    from app.services.enrollment_service import update_enrollment_service

    return update_enrollment_service(
        db, enrollment.enrollment_id, EnrollmentUpdate(state="withdrawn")
    )


@router.get("/students/{student_id}/grades", response_model=list[GradeHistoryItem])
def student_grade_history(
    student_id: int,
    period: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    query = (
        db.query(Grade)
        .join(Grade.enrollment)
        .filter(Enrollment.student_id == student_id, Grade.status != "voided")
    )
    if user.student_id is not None:
        query = query.filter(Grade.status == "published")
    if not has_scope(user, *ACADEMIC_SCOPE) and user.teacher_id is not None:
        query = query.join(Enrollment.section).filter(Section.teacher_id == user.teacher_id)
    if period:
        query = query.filter(Enrollment.period == period)
    grades = query.offset(skip).limit(limit).all()
    return [
        GradeHistoryItem(
            grade_id=grade.grade_id,
            enrollment_id=grade.enrollment_id,
            subject_code=grade.enrollment.section.subject.code,
            section_code=grade.enrollment.section.code,
            period=grade.enrollment.period,
            grade_value=grade.grade_value,
            grade_type=grade.assessment.name if grade.assessment else grade.grade_type,
            date_recorded=grade.date_recorded,
            assessment_weight=grade.assessment.weight if grade.assessment else None,
            contribution=round(grade.grade_value * grade.assessment.weight / 100, 2)
            if grade.assessment and grade.status == "published"
            else None,
        )
        for grade in grades
    ]


@router.get("/students/{student_id}/schedule", response_model=list[ScheduleItem])
def student_schedule(
    student_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    period = period or None
    active = db.query(AcademicPeriod).filter_by(active=True).first()
    if period is None and active is None:
        return []
    current = period is None or (active and period == active.name)
    query = (
        db.query(Section)
        .options(load_schedule())
        .join(Section.enrollments)
        .filter(Enrollment.student_id == student_id, Enrollment.period == (period or active.name))
    )
    if not has_scope(user, *ACADEMIC_SCOPE) and user.teacher_id is not None:
        query = query.filter(Section.teacher_id == user.teacher_id)
    if current:
        query = query.filter(
            Enrollment.state == "enrolled", Section.status.in_(("published", "active"))
        )
    else:
        query = query.filter(
            Enrollment.state.in_(("enrolled", "completed", "failed")),
            Section.status.not_in(("draft", "cancelled")),
        )
    return [schedule_item(section) for section in query.order_by(Section.code).distinct().all()]


@router.get("/teachers/{teacher_id}/schedule", response_model=list[ScheduleItem])
def teacher_schedule(
    teacher_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_teacher_access(user, teacher_id)
    period = period or None
    active = db.query(AcademicPeriod).filter_by(active=True).first()
    if period is None and active is None:
        return []
    current = period is None or (active and period == active.name)
    name = period or active.name
    legacy = Section.enrollments.any(Enrollment.period == name)
    if current:
        legacy = legacy | ~Section.enrollments.any()
    query = (
        db.query(Section)
        .options(load_schedule())
        .filter(
            Section.teacher_id == teacher_id,
            (Section.period_name == name) | ((Section.period_name == "") & legacy),
        )
    )
    if current:
        query = query.filter(Section.status.in_(("published", "active")))
    else:
        query = query.filter(Section.status.not_in(("draft", "cancelled")))
    return [schedule_item(section) for section in query.order_by(Section.code).all()]


@router.get("/sections/{section_id}/students", response_model=list[SectionStudentItem])
def section_students(
    section_id: int,
    period: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_section_access(db, user, section_id)
    query = db.query(Enrollment).filter(
        Enrollment.section_id == section_id,
        Enrollment.state == "enrolled",
    )
    if period:
        query = query.filter(Enrollment.period == period)
    enrollments = query.offset(skip).limit(limit).all()
    return [
        SectionStudentItem(
            student_id=item.student_id,
            enrollment_id=item.enrollment_id,
            enrollment_number=item.student.enrollment_number,
            first_name=item.student.first_name,
            last_name=item.student.last_name,
            state=item.state,
            period=item.period,
        )
        for item in enrollments
    ]


def _percentage(present: int, total: int) -> float | None:
    return round(present * 100 / total, 1) if total else None


@router.get("/sections/academic-summary", response_model=list[SectionAcademicSummary])
def section_academic_summaries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    start: date | None = None,
    end: date | None = None,
):
    if start and end and start > end:
        raise HTTPException(422, "El inicio debe ser anterior al fin")
    query = db.query(Section)
    if not has_scope(user, *ACADEMIC_SCOPE):
        if user.teacher_id is None:
            raise HTTPException(403, "Los resúmenes académicos son solo para el personal")
        query = query.filter(Section.teacher_id == user.teacher_id)
    summaries = []
    for section in query.order_by(Section.code).all():
        active_enrollments = [
            item
            for item in section.enrollments
            if item.state in {"enrolled", "completed", "failed"}
        ]
        attendances = [record for item in active_enrollments for record in item.attendances]
        attendances = [
            r
            for r in attendances
            if (not start or r.date.date() >= start) and (not end or r.date.date() <= end)
        ]
        results = [academic_result(db, item) for item in active_enrollments]
        grades = [result.value for result in results if result.value is not None]
        assessments = db.query(Assessment).filter_by(section_id=section.section_id).all()
        notes = [grade for enrollment in active_enrollments for grade in enrollment.grades]
        summaries.append(
            SectionAcademicSummary(
                section_id=section.section_id,
                section_code=section.code,
                subject_code=section.subject.code,
                subject_name=section.subject.description,
                teacher_name=f"{section.teacher.first_name} {section.teacher.last_name}",
                student_count=len(active_enrollments),
                attendance_percentage=_percentage(
                    sum(record.present for record in attendances), len(attendances)
                ),
                grade_average=round(sum(grades) / len(grades), 1) if grades else None,
                assessment_count=len(assessments),
                period_name=section.period_name,
                graded_student_count=len(grades),
                final_student_count=sum(result.final for result in results),
                pending_student_count=sum(not result.final for result in results),
                draft_grade_count=sum(grade.status == "draft" for grade in notes),
                published_grade_count=sum(grade.status == "published" for grade in notes),
                closed_assessment_count=sum(item.closed for item in assessments),
                configured_weight=sum(item.weight for item in assessments),
                attendance_total=len(attendances),
                attendance_counts={
                    status: sum(r.status == status for r in attendances)
                    for status in ("present", "absent", "late", "excused", "early_departure")
                },
            )
        )
    return summaries


@router.get("/students/{student_id}/profile", response_model=StudentAcademicProfile)
def student_academic_profile(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    summaries = []
    all_grades = []
    total_attendances = 0
    total_present = 0
    for enrollment in student.enrollments:
        if (
            not has_scope(user, *ACADEMIC_SCOPE)
            and user.teacher_id is not None
            and enrollment.section.teacher_id != user.teacher_id
        ):
            continue
        result = academic_result(db, enrollment)
        grades = [result.value] if result.value is not None else []
        attendances = enrollment.attendances
        present = sum(item.present for item in attendances)
        all_grades.extend(grades)
        total_attendances += len(attendances)
        total_present += present
        summaries.append(
            StudentEnrollmentSummary(
                enrollment_id=enrollment.enrollment_id,
                section_id=enrollment.section_id,
                section_code=enrollment.section.code,
                subject_code=enrollment.section.subject.code,
                subject_name=enrollment.section.subject.description,
                period=enrollment.period,
                state=enrollment.state,
                average_grade=result.value,
                result_final=result.final,
                result_status=result.status,
                completed_weight=result.completed_weight,
                calculation_mode=result.mode,
                attendance_percentage=_percentage(present, len(attendances)),
            )
        )
    return StudentAcademicProfile(
        student_id=student.student_id,
        enrollment_number=student.enrollment_number,
        first_name=student.first_name,
        last_name=student.last_name,
        email=student.email,
        telephone=student.telephone,
        address=student.address,
        active=student.active,
        academic_hold=student.academic_hold,
        financial_hold=student.financial_hold,
        document_number=student.document_number,
        birth_date=student.birth_date,
        nationality=student.nationality,
        admission_date=student.admission_date,
        previous_school=student.previous_school,
        emergency_contact_name=student.emergency_contact_name,
        emergency_contact_phone=student.emergency_contact_phone,
        emergency_contact_relationship=student.emergency_contact_relationship,
        career_id=student.career_id,
        career_name=student.career.name,
        overall_average=round(sum(all_grades) / len(all_grades), 1) if all_grades else None,
        overall_attendance=_percentage(total_present, total_attendances),
        enrollments=summaries,
    )


@router.get("/sections/{section_id}/workspace", response_model=SectionWorkspace)
def section_workspace(
    section_id: int,
    attendance_date: date = Query(default_factory=business_date),
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    start: date | None = None,
    end: date | None = None,
):
    if start and end and start > end:
        raise HTTPException(422, "El inicio debe ser anterior al fin")
    section = ensure_section_access(db, user, section_id)
    query = db.query(Enrollment).filter(
        Enrollment.section_id == section_id,
        Enrollment.state.in_(("enrolled", "completed", "failed")),
    )
    if period:
        query = query.filter(Enrollment.period == period)
    roster = []
    for enrollment in query.all():
        grades = [
            RosterGradeItem(
                grade_id=item.grade_id,
                assessment_id=item.assessment_id,
                grade_type=item.assessment.name if item.assessment else item.grade_type,
                status=item.status,
                grade_value=item.grade_value,
                date_recorded=item.date_recorded,
                assessment_weight=item.assessment.weight if item.assessment else None,
                contribution=round(item.grade_value * item.assessment.weight / 100, 2)
                if item.assessment and item.status == "published"
                else None,
            )
            for item in enrollment.grades
        ]
        attendance = next(
            (item for item in enrollment.attendances if item.date.date() == attendance_date), None
        )
        attendance_records = [
            r
            for r in enrollment.attendances
            if (not start or r.date.date() >= start) and (not end or r.date.date() <= end)
        ]
        present = sum(item.present for item in attendance_records)
        result = academic_result(db, enrollment)
        roster.append(
            SectionRosterItem(
                student_id=enrollment.student_id,
                enrollment_id=enrollment.enrollment_id,
                enrollment_number=enrollment.student.enrollment_number,
                first_name=enrollment.student.first_name,
                last_name=enrollment.student.last_name,
                email=enrollment.student.email,
                state=enrollment.state,
                period=enrollment.period,
                grades=grades,
                average_grade=result.value,
                result_final=result.final,
                result_status=result.status,
                completed_weight=result.completed_weight,
                calculation_mode=result.mode,
                attendance_percentage=_percentage(present, len(attendance_records)),
                attendance_status=attendance.present if attendance else None,
                attendances=[
                    RosterAttendanceItem(
                        attendance_id=item.attendance_id,
                        date=item.date.date(),
                        status=item.status,
                        note=item.note,
                        excuse_reference=item.excuse_reference,
                    )
                    for item in sorted(
                        attendance_records, key=lambda record: record.date, reverse=True
                    )
                ],
            )
        )
    schedule = schedule_item(section)
    return SectionWorkspace(
        subject_id=section.subject_id,
        period_name=section.period_name,
        section_id=section.section_id,
        section_code=section.code,
        description=section.description,
        subject_code=section.subject.code,
        subject_name=section.subject.description,
        teacher_name=f"{section.teacher.first_name} {section.teacher.last_name}",
        days_of_week=schedule.days_of_week,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        blocks=schedule.blocks,
        attendance_date=attendance_date,
        roster=roster,
    )


@router.get(
    "/students/{student_id}/attendance-summary", response_model=list[AttendanceCourseSummary]
)
def student_attendance_summary(
    student_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    start: date | None = None,
    end: date | None = None,
):
    if start and end and start > end:
        raise HTTPException(422, "El inicio debe ser anterior al fin")
    ensure_student_academic_access(db, user, student_id)
    query = db.query(Enrollment).filter(Enrollment.student_id == student_id)
    if not has_scope(user, *ACADEMIC_SCOPE) and user.teacher_id is not None:
        query = query.join(Enrollment.section).filter(Section.teacher_id == user.teacher_id)
    if period:
        query = query.filter(Enrollment.period == period)
    results = []
    for item in query.all():
        records = [
            r
            for r in item.attendances
            if (not start or r.date.date() >= start) and (not end or r.date.date() <= end)
        ]
        results.append(
            AttendanceCourseSummary(
                section_id=item.section_id,
                section_code=item.section.code,
                subject_code=item.section.subject.code,
                subject_name=item.section.subject.description,
                present_count=sum(record.present for record in records),
                total_count=len(records),
                percentage=_percentage(sum(record.present for record in records), len(records)),
                enrollment_id=item.enrollment_id,
                period=item.period,
                state=item.state,
                counts={
                    status: sum(r.status == status for r in records)
                    for status in ("present", "absent", "late", "excused", "early_departure")
                },
                records=[
                    RosterAttendanceItem(
                        attendance_id=r.attendance_id,
                        date=r.date.date(),
                        status=r.status,
                        note=r.note,
                        excuse_reference=r.excuse_reference,
                    )
                    for r in sorted(records, key=lambda r: r.date, reverse=True)
                ],
            )
        )
    return results
