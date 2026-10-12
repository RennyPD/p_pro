import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { AssessmentsPage } from "./AssessmentsPage";

function setup() {
  useAuthStore.setState({ user: { user_id: 1, username: "admin", email: "admin@example.com", role_id: 1, role_name: "admin", student_id: null, teacher_id: null }, token: "test" });
  const components = [
    { assessment_id: 11, name: "Parcial", weight: 20, due_date: null, closed: false },
    { assessment_id: 12, name: "Proyecto", weight: 80, due_date: null, closed: false },
  ];
  const get = vi.spyOn(api, "get").mockImplementation(async path => {
    const responses: Record<string, unknown> = {
      "/sections/": [{ section_id: 1, code: "MAT-A", subject_id: 7, subject_name: "Matemática", teacher_name: "Ana Pérez", period_name: "2026-2" }],
      "/assessments/sections/1": components,
      "/academic/sections/1/workspace": { subject_id: 7, roster: [
        { enrollment_id: 5, first_name: "Luis", last_name: "Demo", enrollment_number: "EST-5", grades: [
          { grade_id: 21, assessment_id: 11, grade_value: 0, status: "published" },
          { grade_id: 22, assessment_id: 12, grade_value: 80, status: "draft" },
        ] },
        { enrollment_id: 6, first_name: "Eva", last_name: "Demo", enrollment_number: "EST-6", grades: [] },
      ] },
      "/assessments/sections/1/finals": [{ enrollment_id: 5, weighted_grade: 0, completed_weight: 20, final: false, status: "in_progress" }],
      "/assessments/plans/templates": [],
      "/assessments/templates": [],
    };
    return { data: responses[path] ?? [] } as never;
  });
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: [] } as never);
  const patch = vi.spyOn(api, "patch").mockResolvedValue({ data: components } as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><AssessmentsPage /></MemoryRouter></QueryClientProvider>);
  return { get, post, patch };
}

describe("Assessment workflow", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });
  it("distinguishes a published zero from a missing note and blocks publishing unsaved changes", async () => {
    const { post } = setup();
    const zero = await screen.findByRole("spinbutton", { name: "Parcial de Luis Demo" });
    expect(zero).toHaveValue(0);
    expect(screen.getByRole("spinbutton", { name: "Parcial de Eva Demo" })).toHaveValue(null);
    const publish = screen.getAllByRole("button", { name: "Publicar" });
    expect(publish[1]).toBeEnabled();
    fireEvent.change(zero, { target: { value: "10" } });
    expect(publish[1]).toBeDisabled();
    expect(screen.getByText("Sin guardar")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Ej. Revisión del examen y corrección del puntaje"), { target: { value: "Revisión del examen" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Guardar borrador" })[0]);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/grades/bulk", expect.objectContaining({
      status: "draft", assessment_id: 11, records: [{ enrollment_id: 5, grade_value: 10 }],
    })));
  });
  it("sends redistribution as one operation instead of changing percentages individually", async () => {
    const { patch } = setup();
    await screen.findByRole("spinbutton", { name: "Parcial de Luis Demo" });
    fireEvent.click(screen.getByRole("button", { name: "Distribución y plantillas" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Porcentaje de Parcial" }), { target: { value: "50" } });
    expect(screen.getByRole("button", { name: "Guardar distribución" })).toBeDisabled();
    fireEvent.change(screen.getByRole("spinbutton", { name: "Porcentaje de Proyecto" }), { target: { value: "50" } });
    fireEvent.change(screen.getByPlaceholderText("Ej. Revisión del examen y corrección del puntaje"), { target: { value: "Redistribución aprobada" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar distribución" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/assessments/sections/1/distribution", {
      reason: "Redistribución aprobada", components: [{ assessment_id: 11, weight: 50 }, { assessment_id: 12, weight: 50 }],
    }));
  });
});
