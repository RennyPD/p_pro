"""Recognition without manufactured grades, shared by all academic consumers."""

from dataclasses import dataclass

from app.models.curriculum_model import CurriculumCourse
from app.models.governance_model import CourseEquivalence
from app.services.academic_grading import academic_result


def current_courses(db, student):
    return (
        db.query(CurriculumCourse)
        .filter_by(
            career_id=student.career_id, curriculum_version=student.career.curriculum_version
        )
        .order_by(CurriculumCourse.term_number, CurriculumCourse.curriculum_course_id)
        .all()
    )


@dataclass
class Recognition:
    direct: set[int]
    paths: dict[int, list[int]]
    sources: dict[int, int]

    @property
    def completed(self):
        return self.direct | self.paths.keys()


def recognize(db, student, rules=None):
    direct = {
        e.section.subject_id
        for e in student.enrollments
        if academic_result(db, e).status == "passed"
    }
    plan = {c.subject_id for c in current_courses(db, student)}
    if rules is None:
        rules = (
            db.query(CourseEquivalence)
            .filter_by(
                career_id=student.career_id,
                curriculum_version=student.career.curriculum_version,
                active=True,
            )
            .all()
        )
    rules = sorted(
        (
            r
            for r in rules
            if r.active
            and r.career_id == student.career_id
            and r.curriculum_version == student.career.curriculum_version
            and r.target_subject_id in plan
        ),
        key=lambda r: r.course_equivalence_id or 0,
    )
    result = Recognition(direct, {}, {})
    # Fixed point, independent of insertion order. Finite even for legacy cycles.
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if (
                rule.source_subject_id in result.completed
                and rule.target_subject_id not in result.completed
            ):
                source = rule.source_subject_id
                result.paths[rule.target_subject_id] = result.paths.get(source, []) + [
                    rule.course_equivalence_id or 0
                ]
                result.sources[rule.target_subject_id] = result.sources.get(source, source)
                changed = True
    return result
