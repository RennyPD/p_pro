import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  GraduationCap,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Spinner } from "../../components/ui";
import { describeAverage } from "../../lib/academicResult";
import { api } from "../../lib/api";
import { formatDateTime, formatMoney, formatTime } from "../../lib/format";
import { scheduleBlocks, weekDays } from "../../lib/schedule";
import { useAuthStore } from "../../store/auth";
import { useAccess } from "../../lib/permissions";

type Metric = { key: string; label: string; value: number | null; note: string };
type Summary = {
  display_name?: string;
  active_period: string | null;
  alerts: string[];
  metrics: Metric[];
};
type SectionProgress = {
  section_id: number;
  section_code: string;
  subject_name: string;
  student_count: number;
  final_student_count: number;
  ungraded_student_count?: number;
  draft_grade_count: number;
};
type CareerMetric = {
  career_id: number;
  career_name: string;
  attendance_percentage: number | null;
  average_grade: number | null;
  grade_count: number;
  provisional_average_grade?: number | null;
  provisional_grade_count?: number;
};
type Analytics = { open_alerts: number; receivables: number; admission_pipeline: number };
type Task = {
  assignment_id: number;
  title: string;
  due_at: string;
  subject_name: string;
  lifecycle: string;
  submission: { status: string } | null;
};
type Block = {
  key: string;
  section_id: number;
  subject_code: string;
  subject_name: string;
  section_code: string;
  day: string;
  start: string;
  end: string;
  room: string;
};

const today = new Intl.DateTimeFormat("es-DO", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: "America/Santo_Domingo",
}).format(new Date());
const todayName = (() => {
  const name = new Intl.DateTimeFormat("es-DO", {
    weekday: "long",
    timeZone: "America/Santo_Domingo",
  }).format(new Date());
  return name.charAt(0).toUpperCase() + name.slice(1);
})();
const icons: Record<string, ReactNode> = {
  students: <GraduationCap />,
  teachers: <Users />,
  sections: <CalendarDays />,
  enrollments: <ClipboardCheck />,
  courses: <BookOpen />,
  average: <TrendingUp />,
  attendance: <ClipboardCheck />,
  grades: <BookOpen />,
};
const tones = ["blue", "violet", "amber", "green"];

export function DashboardPage() {
  const { user } = useAuthStore();
  const access = useAccess();
  const summary = useQuery<Summary>({
    queryKey: ["dashboard-summary", user?.user_id, user?.role_name],
    queryFn: () => api.get("/dashboard/summary").then(response => response.data),
    enabled: Boolean(user),
  });
  if (summary.isLoading)
    return (
      <div className="page">
        <Spinner label="Preparando tu espacio" />
      </div>
    );
  const data = summary.data;
  return (
    <div className="page">
      <header className="page-header hero-header">
        <div>
          <span className="kicker">{today}</span>
          <h1>Hola, {data?.display_name || user?.username}</h1>
          <p>
            {data?.active_period
              ? `Período activo: ${data.active_period}`
              : "No hay un período académico activo."}
          </p>
        </div>
      </header>
      {Boolean(data?.alerts?.length) && (
        <section className="dashboard-alerts">
          {data?.alerts.map(alert => (
            <div key={alert}>
              <AlertTriangle />
              {alert}
            </div>
          ))}
        </section>
      )}
      <section className="metric-grid">
        {data?.metrics.map((metric, index) => (
          <MetricCard
            key={metric.key}
            icon={icons[metric.key] ?? <TrendingUp />}
            metric={metric}
            tone={tones[index % tones.length]}
          />
        ))}
      </section>
      {access.institution && access.can("reports.view") && <AdminOverview />}
      {(access.teaching || access.student) && <PersonalDay />}
    </div>
  );
}

/** What needs a decision today, then how each program is doing. */
function AdminOverview() {
  const userId = useAuthStore(state => state.user?.user_id);
  const sections = useQuery<SectionProgress[]>({
    queryKey: ["section-academic-summary", "dashboard", userId],
    queryFn: () => api.get("/academic/sections/academic-summary").then(r => r.data),
  });
  const analytics = useQuery<Analytics>({
    queryKey: ["dashboard-analytics", userId],
    queryFn: () => api.get("/operations/analytics/summary").then(r => r.data),
  });
  const academic = useQuery<{ career_metrics: CareerMetric[] }>({
    queryKey: ["dashboard-academic", userId],
    queryFn: () => api.get("/operations/analytics/academic").then(r => r.data),
  });
  const rows = sections.data ?? [];
  const missing = rows.filter(s => (s.ungraded_student_count ?? 0) > 0).length;
  const closing = rows.filter(
    s =>
      s.student_count > 0 &&
      !(s.ungraded_student_count ?? 0) &&
      s.final_student_count < s.student_count,
  ).length;
  const empty = rows.filter(s => !s.student_count).length;
  const items = [
    missing > 0 && {
      to: "/grades",
      icon: <BookOpen />,
      text: `${missing} ${missing === 1 ? "sección tiene" : "secciones tienen"} notas por completar`,
      tone: "warning",
    },
    closing > 0 && {
      to: "/grades",
      icon: <ClipboardCheck />,
      text: `${closing} ${closing === 1 ? "sección" : "secciones"} con notas completas, por cerrar evaluaciones`,
      tone: "info",
    },
    (analytics.data?.open_alerts ?? 0) > 0 && {
      to: "/institutional-control",
      icon: <AlertTriangle />,
      text: `${analytics.data?.open_alerts} casos de seguimiento abiertos`,
      tone: "warning",
    },
    (analytics.data?.receivables ?? 0) > 0 && {
      to: "/finance",
      icon: <Wallet />,
      text: `${formatMoney(analytics.data?.receivables)} por cobrar`,
      tone: "info",
    },
    (analytics.data?.admission_pipeline ?? 0) > 0 && {
      to: "/institutional-control",
      icon: <Users />,
      text: `${analytics.data?.admission_pipeline} admisiones en proceso`,
      tone: "info",
    },
    empty > 0 && {
      to: "/sections",
      icon: <CalendarDays />,
      text: `${empty} ${empty === 1 ? "sección publicada no tiene" : "secciones publicadas no tienen"} estudiantes`,
      tone: "neutral",
    },
  ].filter(Boolean) as { to: string; icon: ReactNode; text: string; tone: string }[];
  const careers = academic.data?.career_metrics ?? [];
  return (
    <section className="dashboard-grid">
      <article className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Requiere atención</span>
            <h2>Pendientes de la institución</h2>
          </div>
        </div>
        {sections.isLoading || analytics.isLoading ? (
          <Spinner />
        ) : items.length ? (
          <div className="attention-list">
            {items.map(item => (
              <Link
                key={item.text}
                to={item.to}
                className={`attention-item attention-item--${item.tone}`}
              >
                {item.icon}
                <span>{item.text}</span>
                <ArrowRight size={16} />
              </Link>
            ))}
          </div>
        ) : (
          <p className="all-clear">
            <CheckCircle2 /> Todo al día: no hay pendientes abiertos.
          </p>
        )}
      </article>
      <article className="panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Resultados por carrera</span>
            <h2>Asistencia y promedio</h2>
          </div>
        </div>
        {academic.isLoading ? (
          <Spinner />
        ) : careers.length ? (
          <div className="career-bars">
            {careers.map(career => {
              const average = describeAverage({
                finalAverage: career.average_grade,
                finalCount: career.grade_count,
                provisionalAverage: career.provisional_average_grade,
                provisionalCount: career.provisional_grade_count,
              });
              return (
                <div key={career.career_id} className="career-bar">
                  <div className="career-bar__head">
                    <strong>{career.career_name}</strong>
                    <span>
                      {average.kind === "empty"
                        ? "Sin notas"
                        : `Promedio ${average.value}${average.kind === "provisional" ? " (provisional)" : ""}`}
                    </span>
                  </div>
                  <div
                    className="career-bar__track"
                    role="img"
                    aria-label={`Asistencia de ${career.career_name}: ${career.attendance_percentage ?? "sin datos"}%`}
                  >
                    <span style={{ width: `${career.attendance_percentage ?? 0}%` }} />
                  </div>
                  <small>
                    {career.attendance_percentage == null
                      ? "Sin asistencia registrada"
                      : `${career.attendance_percentage}% de asistencia`}
                  </small>
                </div>
              );
            })}
            <Link className="text-link" to="/institutional-control">
              Ver control institucional <ArrowRight size={15} />
            </Link>
          </div>
        ) : (
          <p className="muted">Aún no hay carreras con resultados.</p>
        )}
      </article>
    </section>
  );
}

/** Teacher and student home: today's classes first, then what is pending. */
function PersonalDay() {
  const { user } = useAuthStore();
  const isStudent = useAccess().student;
  const id = isStudent ? user?.student_id : user?.teacher_id;
  const url = isStudent ? `/academic/students/${id}/schedule` : `/academic/teachers/${id}/schedule`;
  const schedule = useQuery<Record<string, never>[]>({
    queryKey: ["my-schedule", user?.user_id, user?.role_name, id],
    queryFn: () => api.get(url).then(r => r.data),
    enabled: Boolean(user && id),
  });
  const blocks: Block[] = (schedule.data ?? []).flatMap((item: Record<string, never>) =>
    scheduleBlocks(item as never).map((block, index) => ({
      key: `${item.section_id}-${index}`,
      section_id: item.section_id,
      subject_code: item.subject_code,
      subject_name: item.subject_name,
      section_code: item.section_code,
      day: block.day_of_week,
      start: block.start_time,
      end: block.end_time,
      room: block.room,
    })),
  );
  const order = (block: Block) =>
    weekDays.indexOf(block.day) * 10000 + Number(block.start.replace(/:/g, "").slice(0, 4));
  const todays = blocks
    .filter(block => block.day === todayName)
    .sort((a, b) => order(a) - order(b));
  const todayIndex = weekDays.indexOf(todayName);
  const upcoming = [...blocks]
    .sort(
      (a, b) =>
        ((weekDays.indexOf(a.day) - todayIndex + 7) % 7) -
          ((weekDays.indexOf(b.day) - todayIndex + 7) % 7) || order(a) - order(b),
    )
    .find(block => block.day !== todayName);
  return (
    <section className="dashboard-grid dashboard-grid--personal">
      <article className="panel day-panel">
        <span className="kicker">Hoy · {todayName}</span>
        <h2>{isStudent ? "Tus clases de hoy" : "Tus secciones de hoy"}</h2>
        {schedule.isLoading ? (
          <Spinner />
        ) : todays.length ? (
          <div className="timeline">
            {todays.map(block => (
              <div className="timeline-item" key={block.key}>
                <span>
                  <Clock3 size={17} />
                  {formatTime(block.start)}
                </span>
                <div>
                  <strong>{block.subject_name}</strong>
                  <small>
                    {block.section_code} · {block.room} · hasta {formatTime(block.end)}
                  </small>
                </div>
                {!isStudent && (
                  <Link className="text-link" to={`/sections/${block.section_id}`}>
                    Pasar lista <ArrowRight size={15} />
                  </Link>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">
            No tienes clases hoy.
            {upcoming
              ? ` Próxima: ${upcoming.subject_name}, ${upcoming.day.toLowerCase()} a las ${formatTime(upcoming.start)}.`
              : ""}
          </p>
        )}
        <Link className="text-link" to="/my-schedule">
          Ver horario semanal <ArrowRight size={15} />
        </Link>
      </article>
      {isStudent ? <StudentPending /> : <TeacherPending />}
    </section>
  );
}

function TeacherPending() {
  const userId = useAuthStore(state => state.user?.user_id);
  const sections = useQuery<SectionProgress[]>({
    queryKey: ["section-academic-summary", "dashboard-teacher", userId],
    queryFn: () => api.get("/academic/sections/academic-summary").then(r => r.data),
  });
  const pending = (sections.data ?? []).filter(
    s =>
      s.student_count > 0 &&
      ((s.ungraded_student_count ?? 0) > 0 ||
        s.draft_grade_count > 0 ||
        s.final_student_count < s.student_count),
  );
  return (
    <article className="panel">
      <span className="kicker">Pendientes</span>
      <h2>Calificaciones por completar</h2>
      {sections.isLoading ? (
        <Spinner />
      ) : pending.length ? (
        <div className="attention-list">
          {pending.map(s => (
            <Link
              key={s.section_id}
              to={`/assessments?section=${s.section_id}`}
              className="attention-item attention-item--info"
            >
              <BookOpen />
              <span>
                <span>
                  <b>{s.subject_name}</b> · {s.section_code}
                </span>
                <small>
                  {(s.ungraded_student_count ?? 0) > 0
                    ? `${s.ungraded_student_count} estudiantes sin notas`
                    : s.draft_grade_count > 0
                      ? `${s.draft_grade_count} notas en borrador`
                      : "Notas completas · falta cerrar evaluaciones"}
                </small>
              </span>
              <ArrowRight size={16} />
            </Link>
          ))}
        </div>
      ) : (
        <p className="all-clear">
          <CheckCircle2 /> Tus secciones están al día.
        </p>
      )}
    </article>
  );
}

function StudentPending() {
  const userId = useAuthStore(state => state.user?.user_id);
  const tasks = useQuery<Task[]>({
    queryKey: ["assignments", "dashboard", userId],
    queryFn: () => api.get("/operations/assignments").then(r => r.data),
  });
  const now = Date.now();
  const upcoming = (tasks.data ?? [])
    .filter(
      task =>
        !task.submission &&
        new Date(task.due_at.endsWith("Z") ? task.due_at : `${task.due_at}Z`).getTime() > now,
    )
    .sort((a, b) => a.due_at.localeCompare(b.due_at))
    .slice(0, 4);
  return (
    <article className="panel">
      <span className="kicker">Pendientes</span>
      <h2>Próximas entregas</h2>
      {tasks.isLoading ? (
        <Spinner />
      ) : upcoming.length ? (
        <div className="attention-list">
          {upcoming.map(task => (
            <Link
              key={task.assignment_id}
              to="/operations"
              className="attention-item attention-item--info"
            >
              <ClipboardCheck />
              <span>
                <span>
                  <b>{task.title}</b> · {task.subject_name}
                </span>
                <small>Vence {formatDateTime(task.due_at)}</small>
              </span>
              <ArrowRight size={16} />
            </Link>
          ))}
        </div>
      ) : (
        <p className="all-clear">
          <CheckCircle2 /> No tienes entregas pendientes.
        </p>
      )}
      <Link className="text-link" to="/my-grades">
        Ver mis notas <ArrowRight size={15} />
      </Link>
    </article>
  );
}

function MetricCard({ icon, metric, tone }: { icon: ReactNode; metric: Metric; tone: string }) {
  return (
    <article className="metric-card">
      <span className={`metric-icon metric-icon--${tone}`}>{icon}</span>
      <div>
        <small>{metric.label}</small>
        <strong>{metric.value === null ? "Sin datos" : metric.value}</strong>
        <span>{metric.note}</span>
      </div>
    </article>
  );
}
