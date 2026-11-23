import { formatDate } from "../../lib/format";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, ClipboardList } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./operations.css";
import { TaskCard } from "./TaskCard";
import { useAccess } from "../../lib/permissions";
import {
  type Section,
  type Task,
  type Event,
  labels,
  date,
  key,
  state,
  tone,
} from "./operationsShared";
import { TaskEditor } from "./TaskEditor";
import { TaskDetail } from "./TaskDetail";
import { EventEditor } from "./EventEditor";

export function OperationsPage() {
  const user = useAuthStore(s => s.user);
  const access = useAccess();
  const manager =
    (access.institution || access.teaching) && access.canAny("tasks.manage", "calendar.manage");
  const client = useQueryClient();
  const [tab, setTab] = useState("tasks"),
    [section, setSection] = useState(""),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("active");
  const [selected, setSelected] = useState<number | null>(null),
    [editor, setEditor] = useState<Task | "new" | null>(null),
    [eventEditor, setEventEditor] = useState<Event | "new" | null>(null);
  const [view, setView] = useState("month"),
    [cursor, setCursor] = useState(new Date()),
    [kind, setKind] = useState(""),
    [clock, setClock] = useState("24");
  const [info, setInfo] = useState<Event | null>(null);
  const [period, setPeriod] = useState("");
  const tasks = useQuery<Task[]>({
    queryKey: ["assignments", user?.user_id],
    queryFn: () => api.get("/operations/assignments").then(r => r.data),
  });
  const agenda = useQuery<Event[]>({
    queryKey: ["agenda", user?.user_id],
    queryFn: () => api.get("/operations/agenda").then(r => r.data),
  });
  const sections = useQuery<Section[]>({
    queryKey: ["task-sections", user?.user_id],
    queryFn: () => api.get("/operations/task-sections").then(r => r.data),
  });
  const refresh = () => {
    for (const queryKey of [["assignments"], ["agenda"], ["task-roster"], ["task-attempts"]])
      client.invalidateQueries({ queryKey });
  };
  const task = tasks.data?.find(t => t.assignment_id === selected);
  const filtered = (tasks.data ?? []).filter(
    t =>
      (!section || t.section_id === Number(section)) &&
      (!period || t.period_name === period) &&
      `${t.title} ${t.subject_name} ${t.section_code}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (filter === "all" ||
        (filter === "active" && t.lifecycle === "open" && t.published) ||
        (filter === "draft" && !t.published) ||
        (filter === "history" && t.lifecycle !== "open") ||
        (filter === "pending" && t.published && t.lifecycle === "open" && !t.submission) ||
        (filter === "graded" && t.submission?.status === "graded") ||
        (filter === "submitted" && Boolean(t.submission) && t.submission?.status !== "graded")),
  );
  const events = (agenda.data ?? []).filter(
    e =>
      (!section || e.section_id === Number(section)) &&
      (!kind || e.kind === kind) &&
      `${e.title} ${e.subject_name}`.toLowerCase().includes(search.toLowerCase()),
  );
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const start =
    view === "week"
      ? new Date(
          cursor.getFullYear(),
          cursor.getMonth(),
          cursor.getDate() - ((cursor.getDay() + 6) % 7),
        )
      : new Date(first.getFullYear(), first.getMonth(), 1 - ((first.getDay() + 6) % 7));
  const days = Array.from(
    { length: view === "week" ? 7 : 42 },
    (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
  );
  const time = (v: string) =>
    date(v).toLocaleTimeString("es-DO", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: clock === "12",
    });
  const shift = (n: number) =>
    setCursor(
      view === "week"
        ? new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + 7 * n)
        : new Date(cursor.getFullYear(), cursor.getMonth() + n, 1),
    );
  const eventButton = (e: Event) => (
    <button
      key={e.id}
      className={`agenda-event agenda-event--${e.kind}`}
      onClick={() => {
        if (e.assignment_id) {
          setTab("tasks");
          setSelected(e.assignment_id);
        } else if (e.event_id) setEventEditor(e);
        else setInfo(e);
      }}
      title={`${e.title} · ${e.subject_name}`}
    >
      <small>
        {labels[e.kind]}
        {!e.all_day && ` · ${time(e.starts_at)}`}
      </small>
      <strong>{e.title}</strong>
      <span>{e.subject_name}</span>
    </button>
  );
  return (
    <div className="page operations-page">
      <header className="page-header">
        <div>
          <span className="kicker">Organización académica</span>
          <h1>Agenda y tareas</h1>
          <p>
            Agenda: fechas importantes. Tareas: actividades, entregas y devoluciones por sección.
          </p>
        </div>
        {manager && (
          <Button onClick={() => (tab === "tasks" ? setEditor("new") : setEventEditor("new"))}>
            {tab === "tasks" ? "Crear tarea" : "Crear evento"}
          </Button>
        )}
      </header>
      <div className="operations-tabs" role="tablist" aria-label="Organización académica">
        <Button
          role="tab"
          aria-selected={tab === "tasks"}
          variant={tab === "tasks" ? "primary" : "secondary"}
          onClick={() => setTab("tasks")}
        >
          Tareas y entregas
        </Button>
        <Button
          role="tab"
          aria-selected={tab === "agenda"}
          variant={tab === "agenda" ? "primary" : "secondary"}
          onClick={() => setTab("agenda")}
        >
          Agenda académica
        </Button>
        {access.institution && access.canAny("reports.view", "cases.manage") && (
          <Link to="/institutional-control">Seguimiento académico →</Link>
        )}
      </div>
      <div className="operations-toolbar">
        <label>
          Sección
          <select value={section} onChange={e => setSection(e.target.value)}>
            <option value="">Todas mis secciones</option>
            {sections.data?.map(s => (
              <option key={s.section_id} value={s.section_id}>
                {s.subject_name} · {s.code} · {s.period_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Buscar
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Título o asignatura"
          />
        </label>
        {tab === "tasks" ? (
          <>
            <label>
              Período
              <select value={period} onChange={e => setPeriod(e.target.value)}>
                <option value="">Todos los períodos</option>
                {Array.from(new Set(tasks.data?.map(t => t.period_name))).map(p => (
                  <option key={p} value={p}>
                    {p || "Sin período asignado"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Mostrar
              <select value={filter} onChange={e => setFilter(e.target.value)}>
                <option value="active">Activas</option>
                {manager && <option value="draft">Borradores</option>}
                {!manager && (
                  <>
                    <option value="pending">Sin entregar</option>
                    <option value="submitted">Entregadas, por revisar</option>
                    <option value="graded">Calificadas</option>
                  </>
                )}
                <option value="history">Cerradas y archivadas</option>
                <option value="all">Todas</option>
              </select>
            </label>
          </>
        ) : (
          <>
            <label>
              Tipo
              <select value={kind} onChange={e => setKind(e.target.value)}>
                <option value="">Todos</option>
                {Object.entries(labels)
                  .slice(0, 7)
                  .map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Hora
              <select value={clock} onChange={e => setClock(e.target.value)}>
                <option value="24">24 horas</option>
                <option value="12">12 horas</option>
              </select>
            </label>
          </>
        )}
      </div>
      {(tasks.error || agenda.error || sections.error) && (
        <p role="alert" className="form-error">
          {apiMessage(tasks.error || agenda.error || sections.error)}
        </p>
      )}
      {tasks.isLoading || agenda.isLoading ? (
        <Spinner />
      ) : tab === "tasks" ? (
        <div className="task-grid">
          {filtered.length ? (
            filtered.map(t => (
              <TaskCard
                key={t.assignment_id}
                task={{
                  title: t.title,
                  instructions: t.instructions,
                  subjectName: t.subject_name,
                  sectionCode: t.section_code,
                  teacherName: t.teacher_name,
                  dueAt: date(t.due_at),
                  maxScore: t.max_score,
                  graded: t.assessment_id !== null,
                  status: state(t),
                  tone: tone(t),
                  submissionCount: manager ? t.submission_count : null,
                }}
                actions={
                  <>
                    <Button onClick={() => setSelected(t.assignment_id)}>
                      {manager ? "Revisar entregas" : "Ver tarea"}
                    </Button>
                    {manager && (
                      <Button variant="secondary" onClick={() => setEditor(t)}>
                        Editar
                      </Button>
                    )}
                  </>
                }
              />
            ))
          ) : (
            <EmptyState
              icon={<ClipboardList />}
              title="Sin tareas en esta vista"
              description="Cambia los filtros o selecciona otra sección."
            />
          )}
        </div>
      ) : (
        <section className="panel">
          <div className="operations-toolbar">
            <Button variant="secondary" onClick={() => shift(-1)} aria-label="Período anterior">
              ←
            </Button>
            <h2>{cursor.toLocaleDateString("es-DO", { month: "long", year: "numeric" })}</h2>
            <Button variant="secondary" onClick={() => shift(1)} aria-label="Período siguiente">
              →
            </Button>
            <Button variant="ghost" onClick={() => setCursor(new Date())}>
              Hoy
            </Button>
            <label>
              Vista
              <select value={view} onChange={e => setView(e.target.value)}>
                <option value="month">Mes</option>
                <option value="week">Semana</option>
                <option value="list">Lista del mes</option>
              </select>
            </label>
          </div>
          <p className="muted">
            El horario recurrente de clases se consulta en Horarios. Aquí aparecen eventos y
            vencimientos.
          </p>
          {view === "list" ? (
            <div className="agenda-list">
              {events
                .filter(
                  e =>
                    date(e.starts_at) < new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1) &&
                    date(e.ends_at) >= first,
                )
                .sort((a, b) => date(a.starts_at).getTime() - date(b.starts_at).getTime())
                .map(e => (
                  <article key={e.id}>
                    <time>{formatDate(e.starts_at)}</time>
                    {eventButton(e)}
                  </article>
                ))}
            </div>
          ) : (
            <div className="agenda-calendar">
              {days.map(d => (
                <div
                  className={`agenda-day ${key(d) === key(new Date()) ? "agenda-day--today" : ""}`}
                  key={key(d)}
                >
                  <time>{d.toLocaleDateString("es-DO", { weekday: "short", day: "numeric" })}</time>
                  {events
                    .filter(e => key(date(e.starts_at)) <= key(d) && key(date(e.ends_at)) >= key(d))
                    .map(eventButton)}
                </div>
              ))}
            </div>
          )}
          {!events.length && (
            <EmptyState
              icon={<CalendarDays />}
              title="Sin fechas registradas"
              description="Los eventos y vencimientos aparecerán aquí."
            />
          )}
        </section>
      )}
      {editor && (
        <TaskEditor
          task={editor}
          sections={sections.data ?? []}
          userId={user?.user_id}
          onClose={() => setEditor(null)}
          onSaved={refresh}
        />
      )}
      {task && (
        <TaskDetail
          task={task}
          manager={manager}
          student={access.student}
          userId={user?.user_id}
          onClose={() => setSelected(null)}
          onSaved={refresh}
        />
      )}
      {eventEditor && (
        <EventEditor
          event={eventEditor}
          sections={sections.data ?? []}
          manager={manager}
          admin={access.institution && access.can("calendar.manage")}
          onClose={() => setEventEditor(null)}
          onSaved={refresh}
        />
      )}
      {info && (
        <Modal title={info.title} onClose={() => setInfo(null)}>
          <p>
            {info.subject_name} · {formatDate(info.starts_at)}
          </p>
          <p>Fecha programada de evaluación. No equivale a una entrega de tarea.</p>
          <Link to={manager ? `/assessments?section=${info.section_id}` : "/my-grades"}>
            {manager ? "Abrir evaluaciones" : "Consultar mis notas"}
          </Link>
        </Modal>
      )}
    </div>
  );
}
