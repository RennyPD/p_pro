import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarDays, GraduationCap, UserRound, Wallet } from "lucide-react";
import { useState } from "react";
import { EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./guardian-portal.css";

type StudentOverview = {
  student_id: number; student_name: string; enrollment_number: string; career_name: string;
  active: boolean; average_grade: number; attendance_percentage: number; balance: number;
  schedule: Array<{ section_id: number; section_code: string; subject_name: string; days_of_week: string; start_time: string; end_time: string; room: string; modality: string }>;
  alerts: Array<{ early_alert_id: number; category: string; severity: string; reason: string; follow_up_date: string | null }>;
};

const money = (value: number) => new Intl.NumberFormat("es-DO", { style: "currency", currency: "DOP" }).format(value);
const time = (value: string) => new Date(`2000-01-01T${value}`).toLocaleTimeString("es-DO", { hour: "numeric", minute: "2-digit" });

export function GuardianPortalPage() {
  const query = useQuery<StudentOverview[]>({ queryKey: ["guardian-overview"], queryFn: () => api.get("/operations/guardian/overview").then(response => response.data) });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  if (query.isLoading) return <div className="page"><Spinner /></div>;
  if (query.error) return <div className="page"><EmptyState icon={<UserRound />} title="No pudimos cargar el seguimiento" description={apiMessage(query.error)} /></div>;
  if (!query.data?.length) return <div className="page"><EmptyState icon={<UserRound />} title="Sin estudiantes vinculados" description="Administración debe asociar al menos un estudiante a esta cuenta familiar." /></div>;
  const student = query.data.find(item => item.student_id === selectedId) ?? query.data[0];

  return <div className="page guardian-page">
    <header className="page-header"><div><span className="kicker">Portal familiar</span><h1>Seguimiento académico</h1><p>Información esencial para acompañar el progreso del estudiante.</p></div>{query.data.length > 1 && <label className="student-switch"><span>Estudiante</span><select value={student.student_id} onChange={event => setSelectedId(Number(event.target.value))}>{query.data.map(item => <option key={item.student_id} value={item.student_id}>{item.student_name}</option>)}</select></label>}</header>
    <section className="guardian-hero"><div><span className="guardian-avatar"><UserRound /></span><div><small>{student.enrollment_number}</small><h2>{student.student_name}</h2><p>{student.career_name}</p></div></div><span className={student.active ? "status-active" : "status-inactive"}>{student.active ? "Activo" : "Inactivo"}</span></section>
    <section className="guardian-metrics"><article><GraduationCap /><span>Promedio</span><strong>{student.average_grade}</strong></article><article><CalendarDays /><span>Asistencia</span><strong>{student.attendance_percentage}%</strong></article><article><AlertTriangle /><span>Alertas abiertas</span><strong>{student.alerts.length}</strong></article><article><Wallet /><span>Balance</span><strong>{money(student.balance)}</strong></article></section>
    <div className="guardian-grid"><section className="panel"><div className="panel-heading"><div><span className="kicker">Semana académica</span><h2>Horario actual</h2></div><CalendarDays /></div>{student.schedule.length ? <div className="guardian-list">{student.schedule.map(item => <article key={item.section_id}><div><strong>{item.subject_name}</strong><small>{item.section_code} · {item.modality === "in_person" ? "Presencial" : item.modality}</small></div><p>{item.days_of_week}<br />{time(item.start_time)}–{time(item.end_time)} · {item.room}</p></article>)}</div> : <p className="muted">No tiene asignaturas seleccionadas actualmente.</p>}</section><section className="panel"><div className="panel-heading"><div><span className="kicker">Acompañamiento</span><h2>Alertas activas</h2></div><AlertTriangle /></div>{student.alerts.length ? <div className="guardian-alerts">{student.alerts.map(alert => <article key={alert.early_alert_id}><div><strong>{alert.category}</strong><span>{alert.severity}</span></div><p>{alert.reason}</p>{alert.follow_up_date && <small>Seguimiento: {new Date(`${alert.follow_up_date}T12:00:00`).toLocaleDateString("es-DO")}</small>}</article>)}</div> : <EmptyState icon={<GraduationCap />} title="Sin alertas abiertas" description="No hay situaciones académicas que requieran atención." />}</section></div>
  </div>;
}
