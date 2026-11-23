import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import ensure_student_access, get_current_user, require_permissions
from app.db.Session import get_db
from app.models.student_model import Student
from app.models.subject_model import Subject
from app.models.user_model import User
from app.schemas.record_schema import AcademicTranscript, PeriodRecord, TranscriptCourse
from app.services.academic_grading import academic_result
from app.services.academic_recognition import current_courses, recognize
from app.services.csv_export import spreadsheet_safe_row
from app.services.grading_scales import academic_index, label, scale_for_student
from app.services.rate_limit import EXPORTS, per_account

router = APIRouter(prefix="/records", tags=["academic records"])

STANDING_LABELS = {
    "honors": "Cuadro de honor",
    "good": "Condición regular",
    "probation": "Observación académica",
    "no_final_results": "Sin resultados definitivos",
}
RESULT_LABELS = {
    "passed": "Aprobada",
    "failed": "Reprobada",
    "in_progress": "Provisional",
    "recognized": "Reconocida por equivalencia",
}


def build_transcript(db: Session, student: Student) -> AcademicTranscript:
    scale = scale_for_student(db, student)
    passing = float(scale.passing_value)
    index_rows = []
    curriculum = {item.subject_id: item for item in current_courses(db, student)}
    attempts: dict[int, int] = {}
    period_values: dict[str, dict[str, float]] = {}
    courses = []
    all_grades = []
    provisional_grades = []
    attempted = 0.0
    earned = 0.0
    credited_subjects = set()
    for enrollment in student.enrollments:
        if enrollment.state in {"withdrawn", "waitlisted"}:
            continue
        subject = enrollment.section.subject
        attempts[subject.subject_id] = attempts.get(subject.subject_id, 0) + 1
        result = academic_result(db, enrollment)
        average = result.value
        credits = enrollment.curriculum_credits
        attempted += credits or 0
        if result.final and average is not None:
            all_grades.append(average)
            index_rows.append((average, credits))
        elif average is not None:
            provisional_grades.append(average)
        passed = result.status == "passed"
        new_credit = passed and credits is not None and subject.subject_id not in credited_subjects
        if new_credit:
            earned += credits
            credited_subjects.add(subject.subject_id)
        bucket = period_values.setdefault(
            enrollment.period,
            {"grade_sum": 0, "grade_count": 0, "attempted": 0, "earned": 0, "courses": 0},
        )
        bucket["attempted"] += credits or 0
        bucket["earned"] += credits if new_credit else 0
        bucket["courses"] += 1
        if result.final and average is not None:
            bucket["grade_sum"] += average
            bucket["grade_count"] += 1
        courses.append(
            TranscriptCourse(
                subject_code=subject.code,
                subject_name=subject.description,
                section_code=enrollment.section.code,
                period=enrollment.period,
                credits=credits,
                curriculum_version=enrollment.curriculum_version,
                average=average,
                average_label=label(scale, average),
                result=result.status,
                attempts=attempts[subject.subject_id],
            )
        )
    recognition = recognize(db, student)
    recognized_credits = 0.0
    for subject_id, rule_ids in sorted(recognition.paths.items()):
        course = curriculum[subject_id]
        recognized_credits += course.credits
        courses.append(
            TranscriptCourse(
                subject_code=course.subject.code,
                subject_name=course.subject.description,
                section_code="Equivalencia",
                period=f"Reconocimiento · Plan {student.curriculum_version}",
                credits=course.credits,
                average=None,
                result="recognized",
                attempts=0,
                recognition_type="equivalence",
                equivalence_ids=rule_ids,
                origin_subject_code=db.get(Subject, recognition.sources[subject_id]).code,
            )
        )
    earned += recognized_credits
    cumulative = round(sum(all_grades) / len(all_grades), 2) if all_grades else None
    provisional = (
        round(sum(provisional_grades) / len(provisional_grades), 2) if provisional_grades else None
    )
    # Standing is only meaningful once there are closed (final) results.
    standing = (
        "no_final_results"
        if cumulative is None
        else "honors"
        if cumulative >= 90
        else "good"
        if cumulative >= passing
        else "probation"
    )
    periods = [
        PeriodRecord(
            period=name,
            average=round(values["grade_sum"] / values["grade_count"], 2)
            if values["grade_count"]
            else None,
            attempted_credits=values["attempted"],
            earned_credits=values["earned"],
            courses=int(values["courses"]),
        )
        for name, values in sorted(period_values.items())
    ]
    return AcademicTranscript(
        grading_scale_name=scale.name,
        academic_index=academic_index(index_rows, scale),
        student_id=student.student_id,
        enrollment_number=student.enrollment_number,
        student_name=f"{student.first_name} {student.last_name}",
        career_name=student.career.name,
        cumulative_average=cumulative,
        final_result_count=len(all_grades),
        provisional_average=provisional,
        provisional_result_count=len(provisional_grades),
        attempted_credits=attempted,
        earned_credits=earned,
        repeated_courses=sum(count - 1 for count in attempts.values() if count > 1),
        academic_standing=standing,
        periods=periods,
        courses=courses,
        recognized_credits=recognized_credits,
        curriculum_version=student.curriculum_version,
        unverified_credit_courses=sum(course.credits is None for course in courses),
    )


@router.get("/students/{student_id}/transcript", response_model=AcademicTranscript)
def student_transcript(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_student_access(user, student_id)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return build_transcript(db, student)


@router.get(
    "/reports/students.csv",
    dependencies=[Depends(per_account(EXPORTS)), Depends(require_permissions("reports.view"))],
)
def student_report(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["matricula", "estudiante", "carrera", "promedio", "creditos_aprobados", "condicion"]
    )
    for student in db.query(Student).order_by(Student.last_name, Student.first_name).all():
        record = build_transcript(db, student)
        writer.writerow(
            spreadsheet_safe_row(
                [
                    record.enrollment_number,
                    record.student_name,
                    record.career_name,
                    record.cumulative_average if record.cumulative_average is not None else "",
                    record.earned_credits,
                    STANDING_LABELS.get(record.academic_standing, record.academic_standing),
                ]
            )
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=expedientes.csv"},
    )
