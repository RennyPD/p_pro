import { useQuery } from "@tanstack/react-query";
import { resultTone } from "../../lib/academicResult";
import { BookCheck } from "lucide-react";
import { Badge, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./assessments.css";
import { gradeText } from "../../lib/grades";

type Course = {
  enrollment_id: number;
  subject_code: string;
  subject_name: string;
  section_code: string;
  period: string;
  state: string;
  average_grade: number | null;
  average_label?: string | null;
  result_final: boolean;
  result_status: string;
  completed_weight: number;
  calculation_mode: string;
};
type PublishedGrade = {
  grade_id: number;
  enrollment_id: number;
  grade_type: string;
  grade_value: number;
  assessment_weight: number | null;
  contribution: number | null;
};
const states: Record<string, string> = {
  passed: "Aprobada",
  failed: "Reprobada",
  in_progress: "Provisional",
  withdrawn: "Retirada",
};

export function StudentGradesPage() {
  const id = useAuthStore(state => state.user?.student_id);
  const query = useQuery({
    queryKey: ["my-grades", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const profile = await api.get<{ enrollments: Course[] }>(`/academic/students/${id}/profile`);
      const grades: PublishedGrade[] = [];
      for (let skip = 0; ; skip += 100) {
        const response = await api.get<PublishedGrade[]>(`/academic/students/${id}/grades`, {
          params: { skip, limit: 100 },
        });
        grades.push(...response.data);
        if (response.data.length < 100) break;
      }
      return {
        courses: profile.data.enrollments.filter(item => item.state !== "waitlisted"),
        grades,
      };
    },
  });
  if (query.isLoading)
    return (
      <div className="page">
        <Spinner />
      </div>
    );
  if (!query.data || query.error)
    return (
      <div className="page">
        <EmptyState
          icon={<BookCheck />}
          title="No pudimos cargar tus resultados"
          description={apiMessage(query.error)}
        />
      </div>
    );
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Resultados publicados</span>
          <h1>Mis calificaciones</h1>
          <p>Tu resultado por asignatura y lo que aporta cada evaluación publicada.</p>
        </div>
      </header>
      <section className="student-grade-grid">
        {query.data.courses.map(course => {
          const grades = query.data.grades.filter(
            grade => grade.enrollment_id === course.enrollment_id,
          );
          const tone = resultTone(course.result_final ? course.result_status : "in_progress");
          return (
            <article className="panel student-grade" key={course.enrollment_id}>
              <header>
                <div>
                  <span className="kicker">
                    {course.subject_code} · {course.section_code}
                  </span>
                  <h2>{course.subject_name}</h2>
                </div>
                <div className={`student-grade__score student-grade__score--${tone}`}>
                  <strong>{gradeText(course.average_grade, course.average_label)}</strong>
                  <Badge tone={tone}>{states[course.result_status] ?? "Provisional"}</Badge>
                </div>
              </header>
              {course.calculation_mode !== "legacy" && (
                <div
                  className="student-grade__bar"
                  role="img"
                  aria-label={`Aporte acumulado ${course.average_grade ?? 0} de 100`}
                >
                  {grades.map(grade => (
                    <span
                      key={grade.grade_id}
                      title={`${grade.grade_type}: aporta ${grade.contribution ?? 0} puntos`}
                      style={{ width: `${grade.contribution ?? 0}%` }}
                    />
                  ))}
                </div>
              )}
              <small className="muted">
                {course.calculation_mode === "legacy"
                  ? "Resultado histórico sin plan ponderado"
                  : course.result_final
                    ? "Resultado definitivo"
                    : course.completed_weight >= 100
                      ? "Notas completas · pendiente del cierre del docente"
                      : `${course.completed_weight}% del plan evaluado`}
              </small>
              {grades.length ? (
                <ul className="student-grade__items">
                  {grades.map(grade => (
                    <li key={grade.grade_id}>
                      <span>
                        {grade.grade_type}
                        <small>
                          {grade.assessment_weight === null
                            ? "Nota histórica"
                            : `Vale ${grade.assessment_weight}% · aporta ${grade.contribution ?? 0}`}
                        </small>
                      </span>
                      <b>{grade.grade_value}</b>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Aún no hay notas publicadas.</p>
              )}
            </article>
          );
        })}
      </section>
      {!query.data.courses.length && (
        <EmptyState
          icon={<BookCheck />}
          title="Todavía no tienes asignaturas"
          description="Selecciona tus asignaturas desde el catálogo académico."
        />
      )}
    </div>
  );
}
