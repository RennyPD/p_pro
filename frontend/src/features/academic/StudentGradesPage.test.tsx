import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { StudentGradesPage } from "./StudentGradesPage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows the weighted result and preserves published zero grades", async () => {
  useAuthStore.setState({ user: { user_id: 3, username: "student", email: "student@example.com", role_id: 3, role_name: "student", student_id: 1, teacher_id: null }, token: "test" });
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: path.endsWith("/profile") ? { enrollments: [{
    enrollment_id: 5, subject_code: "MAT-101", subject_name: "Matemática", section_code: "MAT-A", period: "2026-2", state: "enrolled",
    average_grade: 72, result_final: true, result_status: "passed", completed_weight: 100, calculation_mode: "weighted",
  }] } : [
    { grade_id: 11, enrollment_id: 5, grade_type: "Parcial", grade_value: 0, assessment_weight: 20, contribution: 0 },
    { grade_id: 12, enrollment_id: 5, grade_type: "Proyecto", grade_value: 90, assessment_weight: 80, contribution: 72 },
  ] } as never));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StudentGradesPage /></QueryClientProvider>);
  expect(await screen.findByText("Aprobada")).toBeInTheDocument();
  expect(screen.getByText("Parcial · 0/100")).toBeInTheDocument();
  expect(screen.getByText("80% de la nota · aporta 72 puntos")).toBeInTheDocument();
  expect(screen.getByText("100% del plan con notas publicadas. Resultado definitivo.")).toBeInTheDocument();
});
