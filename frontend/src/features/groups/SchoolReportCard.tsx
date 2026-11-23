import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { ReportCardView, type ReportCard } from "./ReportCardView";

/**
 * The school report card of a student, when they belong to a group; renders
 * nothing for university students (the API answers 404) or while loading.
 */
export function SchoolReportCard({ studentId }: { studentId: number }) {
  const card = useQuery({
    queryKey: ["report-card", studentId, "latest"],
    queryFn: () => api.get<ReportCard>(`/students/${studentId}/report-card`).then(r => r.data),
    retry: false,
  });
  if (!card.data || !Array.isArray(card.data.subjects)) return null;
  return <ReportCardView card={card.data} />;
}
