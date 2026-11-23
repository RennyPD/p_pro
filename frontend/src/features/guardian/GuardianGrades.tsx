import { Progress } from "../../components/visual";
import { Badge } from "../../components/ui";
import { provisionalReason, resultLabel, resultTone } from "../../lib/academicResult";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate } from "../../lib/format";
import { Loaded } from "./guardianShared";
import { useGuardianDetail } from "./guardianData";
import { gradeText } from "../../lib/grades";
import { SchoolReportCard } from "../groups/SchoolReportCard";

type Grades = ApiSchema<"GuardianGrades">;

export function GuardianGrades({ studentId }: { studentId: number }) {
  const query = useGuardianDetail<Grades>(studentId, "grades");
  return (
    <>
      <SchoolReportCard studentId={studentId} />
      <Loaded query={query}>
        {data =>
          data.courses.length ? (
            <ul className="guardian-cards">
              {data.courses.map(course => (
                <li key={course.enrollment_id} className="panel">
                  <details>
                    <summary>
                      <div>
                        <strong>{course.subject_name}</strong>
                        <small>
                          {course.section_code} ·{" "}
                          {course.final
                            ? "Resultado final"
                            : provisionalReason(course.completed_weight, course.configured_weight)}
                        </small>
                      </div>
                      <div className="guardian-result">
                        <span className="guardian-figure">
                          {gradeText(course.result, course.result_label)}
                        </span>
                        <Badge tone={resultTone(course.result_status)}>
                          {resultLabel(course.result_status)}
                        </Badge>
                      </div>
                    </summary>
                    <Progress
                      value={
                        course.configured_weight
                          ? (course.completed_weight * 100) / course.configured_weight
                          : 0
                      }
                      label={`Evaluado en ${course.subject_name}`}
                    />
                    <ul
                      className="guardian-days"
                      aria-label={`Evaluaciones de ${course.subject_name}`}
                    >
                      {course.assessments.map((assessment, index) => (
                        <li key={assessment.assessment_id ?? `grade-${index}`}>
                          <span>
                            {assessment.name}
                            {assessment.weight !== null && assessment.weight !== undefined && (
                              <small> · {assessment.weight}%</small>
                            )}
                          </span>
                          <b>
                            {assessment.grade_value === null || assessment.grade_value === undefined
                              ? "Pendiente"
                              : gradeText(assessment.grade_value, assessment.grade_label)}
                          </b>
                          {assessment.due_date && <small>{formatDate(assessment.due_date)}</small>}
                        </li>
                      ))}
                    </ul>
                  </details>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Sin asignaturas en el período actual.</p>
          )
        }
      </Loaded>
    </>
  );
}
