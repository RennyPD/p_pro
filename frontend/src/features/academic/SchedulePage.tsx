import { useQuery } from "@tanstack/react-query";
import { CalendarDays, List, Rows3 } from "lucide-react";
import { useState } from "react";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { scheduleBlocks, weekDays, type ScheduleTimes } from "../../lib/schedule";
import { useAuthStore } from "../../store/auth";
import "./schedule.css";

type ScheduledSection = ScheduleTimes & {
  section_id: number;
  subject_code: string;
  subject_name: string;
  teacher_name: string;
};
type Period = { period_id: number; name: string; active: boolean };

function formatTime(value: string, clock12: boolean) {
  const [hour, minute] = value.split(":").map(Number);
  if (!clock12) return value.slice(0, 5);
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour >= 12 ? "p. m." : "a. m."}`;
}

function modality(value: string) {
  return value === "virtual" ? "Virtual" : value === "hybrid" ? "Híbrida" : "Presencial";
}

export function SchedulePage() {
  const user = useAuthStore(state => state.user);
  const [view, setView] = useState<"list" | "week">("week");
  const [clock12, setClock12] = useState(true);
  const [period, setPeriod] = useState("");
  const path = user?.role_name === "student"
    ? `/academic/students/${user.student_id}/schedule`
    : `/academic/teachers/${user?.teacher_id}/schedule`;
  const periods = useQuery({
    queryKey: ["periods", "schedule", user?.user_id],
    queryFn: () => api.get<Period[]>("/periods/").then(response => response.data),
  });
  const query = useQuery({
    queryKey: ["my-schedule", user?.user_id, path, period],
    queryFn: () => api.get<ScheduledSection[]>(path, { params: { period: period || undefined } }).then(response => response.data),
    enabled: Boolean(user?.student_id || user?.teacher_id),
  });
  const items = (query.data ?? []).flatMap(section =>
    scheduleBlocks(section).map((block, index) => ({ ...section, ...block, key: `${section.section_id}-${index}` }))
  ).sort((a, b) => weekDays.indexOf(a.day_of_week) - weekDays.indexOf(b.day_of_week) || a.start_time.localeCompare(b.start_time));
  const active = periods.data?.find(candidate => candidate.active);
  // Weekends only appear when there are classes, so the grid fits without horizontal scroll.
  const visibleDays = weekDays.filter((day, index) => index < 5 || items.some(item => item.day_of_week === day));
  return (
    <div className="page">
      <header className="page-header">
        <h1>Mi horario</h1>
        <div className="schedule-actions">
          <Button variant="secondary" onClick={() => setClock12(value => !value)}>{clock12 ? "Usar 24 horas" : "Usar 12 horas"}</Button>
          <Button variant={view === "list" ? "primary" : "secondary"} onClick={() => setView("list")}><List size={17} /> Lista</Button>
          <Button variant={view === "week" ? "primary" : "secondary"} onClick={() => setView("week")}><Rows3 size={17} /> Semana</Button>
        </div>
      </header>
      <label className="form-field">
        <span>Período del horario</span>
        <select value={period} onChange={event => setPeriod(event.target.value)}>
          <option value="">{active ? `Vigente · ${active.name}` : "Período vigente"}</option>
          {periods.data?.filter(item => !item.active).map(item => <option key={item.period_id}>{item.name}</option>)}
        </select>
      </label>
      {periods.error && <p role="alert">No se pudo cargar la lista de períodos. {apiMessage(periods.error)}</p>}
      {query.isLoading ? <Spinner label="Cargando horario" /> : query.error ? (
        <EmptyState icon={<CalendarDays />} title="No pudimos cargar el horario" description={apiMessage(query.error)} />
      ) : !items.length ? (
        <EmptyState icon={<CalendarDays />} title="No hay clases programadas" description={period ? `No hay bloques en ${period}.` : "No hay bloques para el período vigente."} />
      ) : view === "list" ? (
        <section className="schedule-list-view">{items.map(item => (
          <article key={item.key}>
            <div className="schedule-hour"><strong>{formatTime(item.start_time, clock12)}</strong><span>{formatTime(item.end_time, clock12)}</span></div>
            <div><span className="kicker">{item.subject_code}</span><h3>{item.subject_name}</h3>
              <p>{item.teacher_name} · {item.room} · {modality(item.modality)}</p><small>{item.day_of_week}</small></div>
          </article>
        ))}</section>
      ) : (
        <section className="week-grid" style={{ "--week-days": visibleDays.length } as React.CSSProperties}>{visibleDays.map(day => (
          <div className="week-day" key={day}>
            <header>{day}</header>
            {items.filter(item => item.day_of_week === day).map(item => (
              <article key={item.key}>
                <time>{formatTime(item.start_time, clock12)}–{formatTime(item.end_time, clock12)}</time>
                <strong>{item.subject_code}</strong><span>{item.subject_name}</span><small>{item.room} · {modality(item.modality)}</small>
              </article>
            ))}
          </div>
        ))}</section>
      )}
    </div>
  );
}
