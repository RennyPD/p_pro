import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import ensure_student_academic_access, get_current_user, require_roles
from app.db.Session import get_db
from app.models.configuration_model import InstitutionSettings
from app.models.curriculum_model import CurriculumCourse
from app.models.student_model import Student
from app.models.user_model import User
from app.schemas.record_schema import AcademicTranscript, PeriodRecord, TranscriptCourse

router = APIRouter(prefix="/records", tags=["academic records"])


def build_transcript(db: Session, student: Student) -> AcademicTranscript:
    settings = db.get(InstitutionSettings, 1)
    passing = settings.passing_grade if settings else 70.0
    curriculum = {
        item.subject_id: item
        for item in db.query(CurriculumCourse)
        .filter(CurriculumCourse.career_id == student.career_id)
        .all()
    }
    attempts: dict[int, int] = {}
    period_values: dict[str, dict[str, float]] = {}
    courses = []
    all_grades = []
    attempted = 0.0
    earned = 0.0
    for enrollment in student.enrollments:
        subject = enrollment.section.subject
        attempts[subject.subject_id] = attempts.get(subject.subject_id, 0) + 1
        grades = [item.grade_value for item in enrollment.grades]
        average = round(sum(grades) / len(grades), 2) if grades else None
        credits = (
            curriculum.get(subject.subject_id).credits if subject.subject_id in curriculum else 0
        )
        attempted += credits
        if average is not None:
            all_grades.extend(grades)
        passed = average is not None and average >= passing
        if passed:
            earned += credits
        bucket = period_values.setdefault(
            enrollment.period,
            {"grade_sum": 0, "grade_count": 0, "attempted": 0, "earned": 0, "courses": 0},
        )
        bucket["attempted"] += credits
        bucket["earned"] += credits if passed else 0
        bucket["courses"] += 1
        if average is not None:
            bucket["grade_sum"] += average
            bucket["grade_count"] += 1
        courses.append(
            TranscriptCourse(
                subject_code=subject.code,
                subject_name=subject.description,
                section_code=enrollment.section.code,
                period=enrollment.period,
                credits=credits,
                average=average,
                result="passed" if passed else "failed" if average is not None else "in_progress",
                attempts=attempts[subject.subject_id],
            )
        )
    cumulative = round(sum(all_grades) / len(all_grades), 2) if all_grades else 0
    standing = "honors" if cumulative >= 90 else "good" if cumulative >= passing else "probation"
    periods = [
        PeriodRecord(
            period=name,
            average=round(values["grade_sum"] / values["grade_count"], 2)
            if values["grade_count"]
            else 0,
            attempted_credits=values["attempted"],
            earned_credits=values["earned"],
            courses=int(values["courses"]),
        )
        for name, values in sorted(period_values.items())
    ]
    return AcademicTranscript(
        student_id=student.student_id,
        enrollment_number=student.enrollment_number,
        student_name=f"{student.first_name} {student.last_name}",
        career_name=student.career.name,
        cumulative_average=cumulative,
        attempted_credits=attempted,
        earned_credits=earned,
        repeated_courses=sum(count - 1 for count in attempts.values() if count > 1),
        academic_standing=standing,
        periods=periods,
        courses=courses,
    )


@router.get("/students/{student_id}/transcript", response_model=AcademicTranscript)
def student_transcript(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_academic_access(db, user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return build_transcript(db, student)


@router.get("/reports/students.csv", dependencies=[Depends(require_roles("admin"))])
def student_report(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["matricula", "estudiante", "carrera", "promedio", "creditos_aprobados", "condicion"]
    )
    for student in db.query(Student).order_by(Student.last_name, Student.first_name).all():
        record = build_transcript(db, student)
        writer.writerow(
            [
                record.enrollment_number,
                record.student_name,
                record.career_name,
                record.cumulative_average,
                record.earned_credits,
                record.academic_standing,
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=expedientes.csv"},
    )
