from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import (
    ensure_section_access,
    ensure_student_academic_access,
    ensure_teacher_access,
    get_current_user,
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
from app.services.enrollment_service import create_enrollment_service

router = APIRouter(prefix="/academic", tags=["academic queries"])


def schedule_item(section: Section) -> ScheduleItem:
    return ScheduleItem(
        section_id=section.section_id,
        section_code=section.code,
        subject_code=section.subject.code,
        subject_name=section.subject.description,
        teacher_name=f"{section.teacher.first_name} {section.teacher.last_name}",
        room=section.room,
        modality=section.modality,
        days_of_week=section.days_of_week.split(", "),
        start_time=section.start_time,
        end_time=section.end_time,
    )


@router.get("/catalog", response_model=list[CourseOffering])
def course_catalog(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.student_id is None:
        raise HTTPException(
            status_code=403, detail="Course selection is only available to students"
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
        .filter(
            Section.subject_id.in_(list(curriculum)),
            Section.status.in_(("published", "active")),
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
                section_id=section.section_id,
                section_code=section.code,
                subject_id=section.subject_id,
                subject_code=section.subject.code,
                subject_name=section.subject.description,
                teacher_name=f"{section.teacher.first_name} {section.teacher.last_name}",
                credits=course.credits,
                days_of_week=section.days_of_week.split(", "),
                start_time=section.start_time,
                end_time=section.end_time,
                room=section.room,
                modality=section.modality,
                capacity=section.capacity,
                available_seats=max(section.capacity - occupied, 0),
                selection_status=current.get(section.section_id)
                or ("cart" if section.section_id in cart else None)
                or selected_subjects.get(section.subject_id),
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
            status_code=403, detail="Course selection is only available to students"
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
        selected_credits=sum(credits.get(item.section.subject_id, 0) for item in enrollments),
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
            status_code=403, detail="Course selection is only available to students"
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
                credits=credits.get(item.section.subject_id, 0),
                available_seats=max(item.section.capacity - occupied, 0),
                period=period.name,
            )
        )
    return result


@router.post("/catalog/cart/{section_id}")
def add_to_selection_cart(
    section_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if user.student_id is None:
        raise HTTPException(
            status_code=403, detail="Course selection is only available to students"
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None or period.status not in {"registration", "active"}:
        raise HTTPException(status_code=409, detail="Course selection is currently closed")
    section = db.get(Section, section_id)
    student = db.get(Student, user.student_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    if (
        db.query(CurriculumCourse)
        .filter_by(
            career_id=student.career_id,
            subject_id=section.subject_id,
            curriculum_version=student.career.curriculum_version,
        )
        .first()
        is None
    ):
        raise HTTPException(
            status_code=409, detail="This subject is not part of the student's program"
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
        raise HTTPException(status_code=409, detail="This subject is already in the cart")
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
    item = (
        db.query(CourseSelectionCart)
        .filter_by(student_id=user.student_id, section_id=section_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()
    return {"message": "Cart item removed"}


@router.post("/catalog/confirm")
def confirm_selection_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.student_id is None:
        raise HTTPException(
            status_code=403, detail="Course selection is only available to students"
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None:
        raise HTTPException(status_code=409, detail="No active academic period")
    items = (
        db.query(CourseSelectionCart)
        .filter_by(student_id=user.student_id, period=period.name)
        .order_by(CourseSelectionCart.created_at)
        .all()
    )
    confirmed = []
    errors = []
    for item in items:
        section_id = item.section_id
        try:
            enrollment = create_enrollment_service(
                db,
                EnrollmentCreate(
                    student_id=user.student_id, section_id=section_id, period=period.name
                ),
            )
            refreshed = (
                db.query(CourseSelectionCart)
                .filter_by(student_id=user.student_id, section_id=section_id, period=period.name)
                .first()
            )
            if refreshed:
                db.delete(refreshed)
                db.commit()
            confirmed.append(
                {
                    "section_id": section_id,
                    "state": enrollment.state,
                    "waitlist_position": enrollment.waitlist_position,
                }
            )
        except HTTPException as exc:
            db.rollback()
            errors.append({"section_id": section_id, "detail": exc.detail})
    return {"confirmed": confirmed, "errors": errors}


@router.post("/catalog/sections/{section_id}/select")
def select_course(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.student_id is None:
        raise HTTPException(
            status_code=403, detail="Course selection is only available to students"
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    if period is None or period.status not in {"registration", "active"}:
        raise HTTPException(status_code=409, detail="Course selection is currently closed")
    student = db.get(Student, user.student_id)
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    offered_in_program = (
        db.query(CurriculumCourse)
        .filter(
            CurriculumCourse.career_id == student.career_id,
            CurriculumCourse.subject_id == section.subject_id,
            CurriculumCourse.curriculum_version == student.career.curriculum_version,
        )
        .first()
    )
    if offered_in_program is None:
        raise HTTPException(
            status_code=409, detail="This subject is not part of the student's program"
        )
    return create_enrollment_service(
        db,
        EnrollmentCreate(
            student_id=user.student_id,
            section_id=section_id,
            period=period.name,
        ),
    )


@router.post("/catalog/sections/{section_id}/withdraw")
def withdraw_course_selection(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.student_id is None:
        raise HTTPException(
            status_code=403, detail="Course selection is only available to students"
        )
    period = db.query(AcademicPeriod).filter(AcademicPeriod.active.is_(True)).first()
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == user.student_id,
            Enrollment.section_id == section_id,
            Enrollment.period == (period.name if period else ""),
            Enrollment.state.in_(("enrolled", "waitlisted")),
        )
        .first()
    )
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Active course selection not found")
    if period and period.withdrawal_deadline and date.today() > period.withdrawal_deadline:
        raise HTTPException(status_code=409, detail="The withdrawal deadline has passed")
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
    query = db.query(Section).join(Section.enrollments).filter(Enrollment.student_id == student_id)
    if period:
        query = query.filter(Enrollment.period == period)
    return [schedule_item(section) for section in query.distinct().all()]


@router.get("/teachers/{teacher_id}/schedule", response_model=list[ScheduleItem])
def teacher_schedule(
    teacher_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_teacher_access(user, teacher_id)
    return [
        schedule_item(section)
        for section in db.query(Section).filter(Section.teacher_id == teacher_id).all()
    ]


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
    if user.role.name.casefold() == "teacher":
        query = query.filter(Section.teacher_id == user.teacher_id)
    elif user.role.name.casefold() != "admin":
        raise HTTPException(status_code=403, detail="Academic summaries are for staff only")
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
        raise HTTPException(status_code=404, detail="Student not found")
    summaries = []
    all_grades = []
    total_attendances = 0
    total_present = 0
    for enrollment in student.enrollments:
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
    attendance_date: date = Query(default_factory=date.today),
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
    return SectionWorkspace(
        subject_id=section.subject_id,
        period_name=section.period_name,
        section_id=section.section_id,
        section_code=section.code,
        description=section.description,
        subject_code=section.subject.code,
        subject_name=section.subject.description,
        teacher_name=f"{section.teacher.first_name} {section.teacher.last_name}",
        days_of_week=section.days_of_week.split(", "),
        start_time=section.start_time,
        end_time=section.end_time,
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
