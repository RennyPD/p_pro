import { formatMoney } from "../../lib/format";
import "./institutional-control.css";
import "./alert-history.css";

export const alertLabels: Record<string, string> = {
  academic: "Académica",
  attendance: "Asistencia",
  financial: "Financiera",
  behavior: "Convivencia",
  other: "Otra",
};
export const severityNames: Record<string, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
  critical: "Crítica",
};
export const admissionNames: Record<string, string> = {
  submitted: "Recibida",
  review: "En revisión",
  accepted: "Aceptada",
  rejected: "Rechazada",
  enrolled: "Matriculada",
};
export const admissionTones: Record<string, "neutral" | "info" | "success" | "danger" | "warning"> =
  {
    submitted: "neutral",
    review: "warning",
    accepted: "info",
    rejected: "danger",
    enrolled: "success",
  };
export const transitionLabels: Record<string, string> = {
  review: "Pasar a revisión",
  accepted: "Aceptar",
  submitted: "Volver a recibida",
};
export const transitions: Record<string, string[]> = {
  submitted: ["review", "rejected"],
  review: ["accepted", "rejected"],
  accepted: ["review", "rejected"],
  rejected: ["review"],
  enrolled: [],
};
export const interventionTypes = {
  note: "Nota",
  contact: "Contacto",
  meeting: "Reunión",
  referral: "Derivación",
  agreement: "Acuerdo",
};
export type AlertDraft = {
  assigned_to: string;
  follow_up_date: string;
  notes: string;
  action_type?: string;
};
export const studentLookup = {
  endpoint: "/students/",
  valueKey: "student_id",
  labelKeys: ["enrollment_number", "first_name", "last_name"],
  placeholder: "Buscar estudiante",
};
export type GradeMetric = {
  average_grade: number | null;
  grade_count: number;
  provisional_average_grade?: number | null;
  provisional_grade_count?: number;
};
export const metric = (value: number | null | undefined, suffix = "") =>
  value == null ? "Sin datos" : `${value}${suffix}`;
export const money = formatMoney;
