import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";

/** Detail of one linked student from /guardian/students/{id}/{area}. */
export function useGuardianDetail<T>(
  studentId: number,
  area: string,
  params?: Record<string, string | number | undefined>,
) {
  return useQuery<T>({
    queryKey: ["guardian", studentId, area, params],
    queryFn: () =>
      api
        .get(`/guardian/students/${studentId}/${area}`, { params })
        .then(response => response.data),
  });
}

export const percent = (value: number | null | undefined) =>
  value === null || value === undefined ? "Sin datos" : `${value}%`;

export const alertCategories: Record<string, string> = {
  academic: "Académica",
  attendance: "Asistencia",
  financial: "Financiera",
  behavior: "Convivencia",
  other: "Otra",
};

export const alertPriorities: Record<string, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
  critical: "Crítica",
};
