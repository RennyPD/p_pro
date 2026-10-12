import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { EquivalencesPage } from "./EquivalencesPage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const rule = { course_equivalence_id: 1, career_id: 1, career_name: "Ingeniería", career_code: "ING", source_subject_id: 1, source_code: "PROG", source_name: "Programación", target_subject_id: 2, target_code: "MAT", target_name: "Matemática", curriculum_version: "2026", active: true, notes: "Regla del comité" };
const impact = { affected_students: 1, gained_subjects: 1, lost_subjects: 0, students: [{ student_id: 1, student_name: "Luis Demo", enrollment_number: "EST-1", gained: ["MAT"], lost: [], credit_delta: 3 }], truncated: false, applies_to_current_version: true };
function setup() {
  useAuthStore.setState({ user: { user_id: 1, username: "admin", email: "admin@example.com", role_id: 1, role_name: "admin", student_id: null, teacher_id: null }, token: "test" });
  vi.spyOn(api, "get").mockImplementation(async (path) => ({ data: path === "/careers/" ? [{ career_id: 1, code: "ING", name: "Ingeniería" }] : path === "/subjects/" ? [{ subject_id: 1, code: "PROG", description: "Programación" }, { subject_id: 2, code: "MAT", description: "Matemática" }, { subject_id: 3, code: "EXT", description: "Fuera del pensum" }] : String(path).includes("/context/") ? { active_version: "2026", versions: ["2026"], courses: [{ subject_id: 2, code: "MAT", name: "Matemática", version: "2026", credits: 3 }] } : String(path).endsWith("/history") ? [{ audit_log_id: 1, action: "equivalence.created", actor: "admin", detail: "Creada por comité", created_at: "2026-10-12T12:00:00" }] : String(path).endsWith("/impact") ? { ...impact, gained_subjects: 0, lost_subjects: 1 } : [rule] } as never));
  const post = vi.spyOn(api, "post").mockImplementation(async (path) => ({ data: String(path).endsWith("/preview") ? impact : rule } as never));
  const patch = vi.spyOn(api, "patch").mockResolvedValue({ data: rule } as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><EquivalencesPage /></QueryClientProvider>);
  return { post, patch };
}
it("limits destination to the selected plan and requires impact before creation", async () => {
  const { post } = setup();
  await screen.findByText("Reglas de equivalencia");
  fireEvent.change(screen.getByLabelText("Carrera destino"), { target: { value: "1" } });
  await waitFor(() => expect(screen.getByLabelText("Versión del pensum destino")).toHaveValue("2026"));
  expect(screen.getByLabelText("Asignatura que se reconocerá").querySelectorAll("option")).toHaveLength(2);
  fireEvent.change(screen.getByLabelText("Asignatura aprobada de origen"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Asignatura que se reconocerá"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Motivo del registro"), { target: { value: "Comité académico" } });
  fireEvent.click(screen.getByRole("button", { name: "Revisar impacto" }));
  expect(await screen.findByText("Impacto previsto (sin guardar)")).toBeInTheDocument();
  expect(post).toHaveBeenCalledTimes(1);
  expect(post).toHaveBeenCalledWith("/governance/equivalences/preview", expect.objectContaining({ curriculum_version: "2026", target_subject_id: 2 }));
  fireEvent.change(screen.getByLabelText("Observaciones"), { target: { value: "Nuevo criterio" } });
  expect(screen.queryByText("Impacto previsto (sin guardar)")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Revisar impacto" })).toBeInTheDocument();
});
it("keeps state changes gated by impact and displays actor history", async () => {
  const { patch } = setup();
  fireEvent.click(await screen.findByRole("button", { name: "Gestionar regla" }));
  fireEvent.change(screen.getByLabelText("Motivo del cambio"), { target: { value: "Revisión" } });
  fireEvent.click(screen.getByLabelText("Regla activa"));
  expect(screen.getByRole("button", { name: "Confirmar cambios" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Revisar impacto del cambio" }));
  await screen.findByText("Impacto previsto (sin guardar)");
  fireEvent.click(screen.getByRole("button", { name: "Confirmar cambios" }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/governance/equivalences/1", { active: false, reason: "Revisión", notes: "Regla del comité" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "Historial" }));
  expect(await screen.findByText("Registro · admin")).toBeInTheDocument();
  expect(screen.getByText("Creada por comité")).toBeInTheDocument();
});
