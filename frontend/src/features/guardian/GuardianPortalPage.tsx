import { RequestApproval } from "../operations/ApprovalsPage";
import { describeAverage } from "../../lib/academicResult";
import { scheduleBlocks, type ScheduleBlock } from "../../lib/schedule";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarDays, GraduationCap, UserRound, Wallet } from "lucide-react";
import { useState } from "react";
import { EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./guardian-portal.css";

type StudentOverview = {
  student_id: number; student_name: string; enrollment_number: string; career_name: string;
  active: boolean; average_grade: number | null; provisional_average_grade?: number | null; final_grade_count?: number; provisional_grade_count?: number; attendance_percentage: number | null; attendance_count?: number; metrics_period?: string | null; balance: number;
  schedule: Array<{ section_id: number; section_code: string; subject_name: string; days_of_week: string; start_time: string; end_time: string; room: string; modality: string; blocks?: ScheduleBlock[] }>;
  alerts: Array<{ early_alert_id: number; category: string; severity: string; reason: string; follow_up_date: string | null }>;
};

const categories: Record<string, string> = { academic: "Académica", attendance: "Asistencia", financial: "Financiera", behavior: "Convivencia", other: "Otra" };
const priorities: Record<string, string> = { low: "Baja", medium: "Media", high: "Alta", critical: "Crítica" };
const modalities: Record<string, string> = { in_person: "Presencial", virtual: "Virtual", hybrid: "Híbrida" };
const money = (value: number) => new Intl.NumberFormat("es-DO", { style: "currency", currency: "DOP" }).format(value);
const time = (value: string) => new Date(`2000-01-01T${value}`).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" });

export function GuardianPortalPage() {
  const query = useQuery<StudentOverview[]>({ queryKey: ["guardian-overview"], queryFn: () => api.get("/operations/guardian/overview").then(response => response.data) });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  if (query.isLoading) return <div className="page"><Spinner /></div>;
  if (query.error) return <div className="page"><EmptyState icon={<UserRound />} title="No pudimos cargar el seguimiento" description={apiMessage(query.error)} /></div>;
  if (!query.data?.length) return <div className="page"><EmptyState icon={<UserRound />} title="Sin estudiantes vinculados" description="Administración debe asociar al menos un estudiante a esta cuenta familiar." /></div>;
  const student = query.data.find(item => item.student_id === selectedId) ?? query.data[0];
  const average = describeAverage({ finalAverage: student.average_grade, finalCount: student.final_grade_count, provisionalAverage: student.provisional_average_grade, provisionalCount: student.provisional_grade_count });
  const today = new Date().toLocaleDateString("en-CA");

  return <div className="page guardian-page">
    <header className="page-header"><div><span className="kicker">Portal familiar</span><h1>Seguimiento académico</h1><p>Información esencial para acompañar el progreso del estudiante.</p></div><div className="guardian-actions">{query.data.length > 1 && <label className="student-switch"><span>Estudiante</span><select value={student.student_id} onChange={event => setSelectedId(Number(event.target.value))}>{query.data.map(item => <option key={item.student_id} value={item.student_id}>{item.student_name} · {item.enrollment_number}</option>)}</select></label>}<RequestApproval resource="student" id={student.student_id} label={`${student.student_name} · ${student.enrollment_number}`} /></div></header>
    <section className="guardian-hero"><div><span className="guardian-avatar"><UserRound /></span><div><small>{student.enrollment_number}</small><h2>{student.student_name}</h2><p>{student.career_name}</p></div></div><span className={student.active ? "status-active" : "status-inactive"}>{student.active ? "Activo" : "Inactivo"}</span></section>
    <section className="guardian-metrics"><article><span><GraduationCap />{average.kind === "provisional" ? "Promedio provisional" : "Promedio"}</span><strong>{average.value}</strong><small>{average.note} · {student.metrics_period ?? "Sin período vigente"}</small></article><article><span><CalendarDays />Asistencia</span><strong>{student.attendance_percentage === null ? "Sin datos" : `${student.attendance_percentage}%`}</strong><small>{student.attendance_count ?? 0} clases registradas</small></article><article><span><AlertTriangle />Alertas abiertas</span><strong>{student.alerts.length}</strong><small>{student.alerts.length ? "Requieren acompañamiento" : "Sin situaciones abiertas"}</small></article><article><span><Wallet />Balance pendiente</span><strong>{money(student.balance)}</strong><small>{student.balance > 0 ? "Consulta con caja institucional" : "Al día"}</small></article></section>
    <div className="guardian-grid"><section className="panel"><div className="panel-heading"><div><span className="kicker">Semana académica</span><h2>Horario actual</h2></div><CalendarDays /></div>{student.schedule.length ? <div className="guardian-list">{student.schedule.map(item => <article key={item.section_id}><div><strong>{item.subject_name}</strong><small>{item.section_code} · {modalities[item.modality] ?? "Modalidad no especificada"}</small></div><div>{scheduleBlocks(item).map((block, index) => <p key={index}><b>{block.day_of_week}</b> {time(block.start_time)}–{time(block.end_time)} · {block.room}</p>)}</div></article>)}</div> : <p className="muted">No tiene asignaturas seleccionadas actualmente.</p>}</section><section className="panel"><div className="panel-heading"><div><span className="kicker">Acompañamiento</span><h2>Alertas activas</h2></div><AlertTriangle /></div>{student.alerts.length ? <div className="guardian-alerts">{student.alerts.map(alert => <article key={alert.early_alert_id}><div><strong>{categories[alert.category] ?? "Otra"}</strong><span>Prioridad {priorities[alert.severity] ?? "No especificada"}</span></div><p>{alert.reason}</p>{alert.follow_up_date && <small className={alert.follow_up_date < today ? "is-overdue" : ""}>{alert.follow_up_date < today ? "Seguimiento vencido desde el" : "Próximo seguimiento:"} {new Date(`${alert.follow_up_date}T12:00:00`).toLocaleDateString("es-DO", { day: "numeric", month: "short", year: "numeric" })}</small>}</article>)}</div> : <EmptyState icon={<GraduationCap />} title="Sin alertas abiertas" description="No hay situaciones académicas que requieran atención." />}</section></div>
  </div>;
}
