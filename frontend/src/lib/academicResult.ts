/**
 * Shared vocabulary for academic results.
 *
 * Every screen uses the same three states so numbers never contradict each other:
 * - "Sin notas": no published grade yet.
 * - "Provisional": published grades exist, but the plan is incomplete or its
 *   assessments are not closed yet. It is never an approval.
 * - "Definitivo": all assessments are published and closed (passed / failed).
 */

export const resultLabels: Record<string, string> = {
  in_progress: "Provisional",
  passed: "Aprobada",
  failed: "Reprobada",
  recognized: "Reconocida por equivalencia",
  withdrawn: "Retirada",
  waitlisted: "En lista de espera",
};

export const standingLabels: Record<string, string> = {
  honors: "Cuadro de honor",
  good: "Condición regular",
  probation: "Observación académica",
  no_final_results: "Sin resultados definitivos",
};

export function resultLabel(status: string | null | undefined) {
  return status ? (resultLabels[status] ?? status) : "Sin notas";
}

export function standingLabel(standing: string | null | undefined) {
  return standing ? (standingLabels[standing] ?? standing) : standingLabels.no_final_results;
}

export type AverageSummary = {
  finalAverage: number | null | undefined;
  finalCount?: number;
  provisionalAverage?: number | null;
  provisionalCount?: number;
};

export type AverageDisplay = {
  value: string;
  note: string;
  kind: "final" | "provisional" | "empty";
};

const plural = (count: number, singular: string, pluralForm = `${singular}s`) =>
  `${count} ${count === 1 ? singular : pluralForm}`;

/** Prefers final results; falls back to a clearly labelled provisional average. */
export function describeAverage({
  finalAverage,
  finalCount = 0,
  provisionalAverage,
  provisionalCount = 0,
}: AverageSummary): AverageDisplay {
  if (finalAverage != null) {
    const pending = provisionalCount
      ? ` · ${plural(provisionalCount, "provisional", "provisionales")} aparte`
      : "";
    return {
      value: String(finalAverage),
      note: `${plural(finalCount, "resultado definitivo", "resultados definitivos")}${pending}`,
      kind: "final",
    };
  }
  if (provisionalAverage != null) {
    return {
      value: String(provisionalAverage),
      note: plural(provisionalCount, "resultado sin cierre", "resultados sin cierre"),
      kind: "provisional",
    };
  }
  return { value: "Sin datos", note: "Sin notas publicadas", kind: "empty" };
}

/** Explains why a weighted result is still provisional. */
export function provisionalReason(completedWeight: number, configuredWeight = 100) {
  if (!completedWeight) return "Sin notas publicadas";
  if (completedWeight < configuredWeight) return `${completedWeight}% del plan publicado`;
  return "Plan completo · falta cerrar evaluaciones";
}

export type Tone = "neutral" | "success" | "warning" | "danger" | "info";

/** Same colours for a result in every profile (student, guardian, teacher, admin). */
export const resultTones: Record<string, Tone> = {
  passed: "success",
  failed: "danger",
  in_progress: "info",
  recognized: "neutral",
  withdrawn: "neutral",
  waitlisted: "warning",
};
export const resultTone = (status: string | null | undefined): Tone =>
  (status && resultTones[status]) || "neutral";

export const attendanceTones: Record<string, Tone> = {
  present: "success",
  absent: "danger",
  late: "warning",
  early_departure: "warning",
  excused: "info",
};

/** Attendance under this percentage is shown as a warning everywhere. */
export const LOW_ATTENDANCE = 80;
export const isLowAttendance = (value: number | null | undefined) =>
  value !== null && value !== undefined && value < LOW_ATTENDANCE;
