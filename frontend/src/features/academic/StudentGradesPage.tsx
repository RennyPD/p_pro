import { useQuery } from "@tanstack/react-query";
import { BookCheck } from "lucide-react";
import { Badge, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./assessments.css";

type Course = { enrollment_id: number; subject_code: string; subject_name: string; section_code: string; period: string;
  state: string; average_grade: number | null; result_final: boolean; result_status: string; completed_weight: number; calculation_mode: string };
type PublishedGrade = { grade_id: number; enrollment_id: number; grade_type: string; grade_value: number; assessment_weight: number | null; contribution: number | null };
const states: Record<string, string> = { passed: "Aprobada", failed: "Reprobada", in_progress: "Provisional", withdrawn: "Retirada" };

export function StudentGradesPage() {
  const id = useAuthStore(state => state.user?.student_id);
  const query = useQuery({ queryKey: ["my-grades", id], enabled: Boolean(id), queryFn: async () => {
    const profile = await api.get<{ enrollments: Course[] }>(`/academic/students/${id}/profile`);
    const grades: PublishedGrade[] = [];
    for (let skip = 0; ; skip += 100) {
      const response = await api.get<PublishedGrade[]>(`/academic/students/${id}/grades`, { params: { skip, limit: 100 } });
      grades.push(...response.data);
      if (response.data.length < 100) break;
    }
    return { courses: profile.data.enrollments.filter(item => item.state !== "waitlisted"), grades };
  } });
  if (query.isLoading) return <div className="page"><Spinner /></div>;
  if (!query.data || query.error) return <div className="page"><EmptyState icon={<BookCheck />} title="No pudimos cargar tus resultados" description={apiMessage(query.error)} /></div>;
  return <div className="page"><header className="page-header"><div><span className="kicker">Resultados publicados</span><h1>Mis calificaciones</h1><p>Consulta cada evaluación y su aporte a tu resultado. Los borradores del docente no aparecen aquí.</p></div></header>
    <section className="assessment-actions">{query.data.courses.map(course => <article className="panel assessment-plan" key={course.enrollment_id}>
      <span className="kicker">{course.subject_code} · {course.section_code} · {course.period}</span><h2>{course.subject_name}</h2>
      <p><strong>{course.average_grade ?? "—"}</strong> / 100 · <Badge tone={course.result_final ? course.result_status === "passed" ? "success" : "danger" : "info"}>{states[course.result_status] ?? "Provisional"}</Badge></p>
      <p className="muted">{course.calculation_mode === "legacy" ? "Resultado histórico sin plan ponderado" : `${course.completed_weight}% del plan con notas publicadas. ${course.result_final ? "Resultado definitivo." : "Todavía no es una aprobación definitiva."}`}</p>
      {query.data.grades.filter(grade => grade.enrollment_id === course.enrollment_id).map(grade => <div className="assessment-template" key={grade.grade_id}>
        <strong>{grade.grade_type} · {grade.grade_value}/100</strong><small>{grade.assessment_weight === null ? "Nota histórica" : `${grade.assessment_weight}% de la nota · aporta ${grade.contribution ?? 0} puntos`}</small>
      </div>)}
      {!query.data.grades.some(grade => grade.enrollment_id === course.enrollment_id) && <p className="muted">Aún no hay notas publicadas.</p>}
    </article>)}</section>
    {!query.data.courses.length && <EmptyState icon={<BookCheck />} title="Todavía no tienes asignaturas" description="Selecciona tus asignaturas desde el catálogo académico." />}
  </div>;
}
