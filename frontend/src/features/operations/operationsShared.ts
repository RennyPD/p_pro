import "./operations.css";
import { type TaskTone } from "./TaskCard";

export type Section = {
  section_id: number;
  code: string;
  subject_name: string;
  period_name: string;
};
export type Submission = {
  submission_id: number;
  content: string;
  submitted_at: string;
  status: string;
  score: number | null;
  feedback: string;
  attempts: number;
};
export type Task = {
  assignment_id: number;
  section_id: number;
  title: string;
  instructions: string;
  due_at: string;
  max_score: number;
  assessment_id: number | null;
  published: boolean;
  lifecycle: string;
  allow_late: boolean;
  allow_resubmit: boolean;
  subject_name: string;
  section_code: string;
  teacher_name: string;
  period_name: string;
  submission: Submission | null;
  submission_count: number | null;
};
export type Event = {
  id: string;
  event_id?: number;
  assignment_id?: number;
  title: string;
  description?: string;
  kind: string;
  starts_at: string;
  ends_at: string;
  section_id: number | null;
  subject_name: string;
  audience?: string;
  no_school?: boolean;
  all_day?: boolean;
};
export type Row = {
  student_id: number;
  student_name: string;
  enrollment_number: string;
  submission: Submission | null;
};
export const labels: Record<string, string> = {
  activity: "Actividad",
  exam: "Examen",
  meeting: "Reunión",
  deadline: "Fecha límite",
  holiday: "Día no lectivo",
  task: "Entrega de tarea",
  assessment: "Evaluación",
  submitted: "Entregada",
  resubmitted: "Reenviada",
  graded: "Calificada",
  open: "Abierta",
  closed: "Cerrada",
  archived: "Archivada",
};
export const date = (v: string) =>
  new Date(v.length === 10 ? `${v}T12:00:00` : /(?:Z|[+-]\d\d:\d\d)$/.test(v) ? v : `${v}Z`);
export const key = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const inputDate = (v: string) => {
  const d = date(v);
  return `${key(d)}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};
export const state = (t: Task) =>
  !t.published
    ? "Borrador"
    : t.lifecycle !== "open"
      ? labels[t.lifecycle]
      : t.submission
        ? labels[t.submission.status]
        : date(t.due_at) < new Date()
          ? "Vencida"
          : "Pendiente";
export const tone = (t: Task): TaskTone => {
  if (!t.published || t.lifecycle !== "open") return "neutral";
  if (t.submission) return t.submission.status === "graded" ? "success" : "info";
  return date(t.due_at) < new Date() ? "danger" : "warning";
};
