import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { SectionResultsDetailPage, SectionResultsPage } from "./SectionResultsPages";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const context = { section_id: 1, section_code: "MAT-A", subject_code: "MAT", subject_name: "Matemática", teacher_name: "Ana Pérez", period_name: "2026-2" };
function renderPage(detail: boolean, data: unknown) {
  useAuthStore.setState({ user: { user_id: 2, username: "docente", email: "docente@example.com", role_id: 2, role_name: "teacher", teacher_id: 1, student_id: null }, token: "test" });
  vi.spyOn(api, "get").mockResolvedValue({ data } as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[detail ? "/section-results/1/grades" : "/grades"]}><Routes><Route path="/grades" element={<SectionResultsPage mode="grades" />} /><Route path="/section-results/:sectionId/:mode" element={<SectionResultsDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>);
  return client;
}

it("explains the summary denominator and filters sections with drafts", async () => {
  const client = renderPage(false, [{ ...context, student_count: 2, grade_average: 32, graded_student_count: 1, final_student_count: 0, pending_student_count: 2, draft_grade_count: 1, published_grade_count: 1, assessment_count: 2, closed_assessment_count: 0, configured_weight: 100 }]);
  expect(await screen.findByText("Matemática")).toBeInTheDocument();
  expect(screen.getByText(/Media sobre 1 de 2 estudiantes/)).toBeInTheDocument();
  expect(screen.getByText("0/2 evaluaciones cerradas · plan 100%")).toBeInTheDocument();
  expect(client.getQueryData(["section-academic-summary", 2, "", ""])).toBeDefined();
  fireEvent.change(screen.getByLabelText("Seguimiento"), { target: { value: "final" } });
  expect(screen.getByText("Sin secciones en esta vista")).toBeInTheDocument();
});

it("distinguishes weighted contributions, drafts and annulled history", async () => {
  const client = renderPage(true, { ...context, roster: [{ enrollment_id: 5, first_name: "Luis", last_name: "Demo", enrollment_number: "EST-5", period: "2026-2", state: "completed", average_grade: 0, result_final: false, result_status: "in_progress", completed_weight: 40, calculation_mode: "weighted", attendance_percentage: null, attendances: [], grades: [
    { grade_id: 1, grade_type: "Parcial", grade_value: 0, date_recorded: "2026-10-12", status: "published", assessment_weight: 40, contribution: 0 },
    { grade_id: 2, grade_type: "Proyecto", grade_value: 90, date_recorded: "2026-10-12", status: "draft", assessment_weight: 60, contribution: null },
    { grade_id: 3, grade_type: "Nota anulada", grade_value: 50, date_recorded: "2026-10-10", status: "voided", assessment_weight: null, contribution: null },
  ] }] });
  expect(await screen.findByText("Luis Demo")).toBeInTheDocument();
  expect(screen.getByText("40% del plan con notas publicadas.")).toBeInTheDocument();
  expect(screen.getByText("Aporta 0 puntos al resultado")).toBeInTheDocument();
  expect(screen.getByText("Borrador")).toBeInTheDocument();
  expect(screen.getByText("Historial de notas anuladas (1)")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Abrir libro de notas" })).toHaveAttribute("href", "/assessments?section=1");
  expect(client.getQueryData(["section-results", "1", 2, "", ""])).toBeDefined();
  fireEvent.change(screen.getByLabelText("Buscar estudiante"), { target: { value: "Eva" } });
  expect(screen.getByText("Sin estudiantes en esta vista")).toBeInTheDocument();
});
