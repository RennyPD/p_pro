import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { CommunityPage } from "../community/CommunityPage";
import { AccessSettingsPage } from "./AccessSettingsPage";
import { InstitutionSettingsPage } from "./InstitutionSettingsPage";
import { InstitutionalControlPage } from "./InstitutionalControlPage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function renderPage(page: ReactNode, teacher = false) {
  useAuthStore.setState({ user: { user_id: teacher ? 2 : 1, username: "demo", email: "demo@example.com", role_id: teacher ? 2 : 1, role_name: teacher ? "teacher" : "admin", student_id: null, teacher_id: teacher ? 1 : null } });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter>{page}</MemoryRouter></QueryClientProvider>);
}
it("lets teachers select their section and preview the audience before publishing", async () => {
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: String(path).endsWith("/sections") ? [{ section_id: 1, label: "MAT-A · Matemática" }] : [] } as never));
  const post = vi.spyOn(api, "post").mockImplementation(async path => ({ data: String(path).endsWith("/preview") ? { count: 2, fingerprint: "destinatarios", roles: { student: 2 } } : {} } as never));
  renderPage(<CommunityPage />, true);
  fireEvent.click(screen.getByRole("button", { name: "Nuevo aviso" }));
  fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Recordatorio" } });
  fireEvent.change(screen.getByLabelText("Mensaje"), { target: { value: "Revisar materiales" } });
  await screen.findByRole("option", { name: "MAT-A · Matemática" });
  expect(screen.getByLabelText("Destinatarios")).toHaveValue("section");
  expect(screen.queryByRole("option", { name: "Toda la institución" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Sección destinataria"), { target: { value: "1" } });
  fireEvent.click(screen.getByRole("button", { name: "Revisar destinatarios" }));
  expect(await screen.findByText("2 destinatarios elegibles")).toBeInTheDocument();
  expect(post).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Confirmar publicación" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/community/announcements", expect.objectContaining({ audience: "section", section_id: 1, expected_recipients: "destinatarios" })));
});
it("shows missing academic samples as no data and keeps permissions outside institutional control", async () => {
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: String(path).endsWith("/summary") ? { students: 10, active_students: 8, open_alerts: 0, receivables: 100 } : String(path).endsWith("/academic") ? { risk_summary: { institutional_retention: 80 }, career_metrics: [{ career_id: 1, career_code: "ING", career_name: "Ingeniería", student_count: 0, active_count: 0, retention_percentage: null, average_grade: null, grade_count: 0, attendance_percentage: null, attendance_count: 0, open_alerts: 0 }], subject_metrics: [] } : [] } as never));
  renderPage(<InstitutionalControlPage />);
  expect(await screen.findByRole("heading", { name: "Ingeniería" })).toBeInTheDocument();
  const average = screen.getByText("Promedio final").parentElement!;
  expect(average).toHaveTextContent("Sin datos");
  expect(average).toHaveTextContent("0 resultados");
  expect(screen.getByRole("link", { name: "Gestionar permisos en Configuración" })).toHaveAttribute("href", "/settings/access");
  expect(screen.queryByRole("button", { name: "Guardar permisos" })).not.toBeInTheDocument();
  expect(screen.getByText("Proporción de estudiantes activos")).toBeInTheDocument();
});
it("limits admission transitions and requires a reason before applying them", async () => {
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: String(path).endsWith("/summary") ? {} : String(path).endsWith("/academic") ? { risk_summary: {}, career_metrics: [], subject_metrics: [] } : String(path).endsWith("/admissions") ? [{ admission_application_id: 1, first_name: "Paula", last_name: "Demo", status: "submitted", career_name: "Ingeniería", email: "paula@example.com" }] : [] } as never));
  const patch = vi.spyOn(api, "patch").mockResolvedValue({ data: {} } as never);
  renderPage(<InstitutionalControlPage />);
  fireEvent.click(screen.getByRole("button", { name: "Admisiones" }));
  const select = await screen.findByRole("combobox", { name: "Estado de Paula Demo" });
  expect(select.querySelectorAll("option")).toHaveLength(3);
  fireEvent.change(select, { target: { value: "review" } });
  fireEvent.change(screen.getByLabelText("Motivo de la transición"), { target: { value: "Documentos recibidos" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar cambio" }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/operations/admissions/1", { status: "review", expected_status: "submitted", reason: "Documentos recibidos" }));
});
it("previews configuration impact and clears the preview when a field changes", async () => {
  const settings = { settings_id: 1, institution_name: "Instituto", enrollment_prefix: "EST", enrollment_digits: 4, passing_grade: 70, max_credits_per_period: 24, revision: 0, next_enrollment_number: 1, enrollment_preview: "EST-2026-0001" };
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: String(path).endsWith("/history") ? [] : settings } as never));
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: { revision: 0, existing_selections_preserved: 12, policy: "Las selecciones conservan su criterio", changes: [{ field: "passing_grade", before: 70, after: 95 }] } } as never);
  renderPage(<InstitutionSettingsPage />);
  const grade = await screen.findByLabelText("Nota aprobatoria para nuevas selecciones");
  await waitFor(() => expect(grade).toHaveValue(70));
  fireEvent.change(grade, { target: { value: "95" } });
  fireEvent.change(screen.getByLabelText("Motivo del cambio institucional"), { target: { value: "Acuerdo académico" } });
  fireEvent.click(screen.getByRole("button", { name: "Revisar impacto" }));
  expect(await screen.findByText("12 selecciones conservarán su criterio aprobatorio.")).toBeInTheDocument();
  expect(post).toHaveBeenCalledWith("/configuration/institution/preview", expect.objectContaining({ passing_grade: 95, expected_revision: 0 }));
  fireEvent.change(grade, { target: { value: "90" } });
  expect(screen.queryByText("Revisión antes de guardar")).not.toBeInTheDocument();
});
it("protects a dirty role draft when switching roles is refused", async () => {
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: path === "/roles/" ? [{ role_id: 1, name: "admin" }, { role_id: 2, name: "teacher" }] : path === "/access/permissions" ? [{ permission_id: 1, slug: "reports.view", description: "Consultar reportes" }] : String(path).endsWith("/permissions") ? { permissions: [] } : [] } as never));
  renderPage(<AccessSettingsPage />);
  const checkbox = await screen.findByRole("checkbox", { name: /Consultar reportes/ });
  fireEvent.click(checkbox);
  expect(checkbox).toBeChecked();
  vi.spyOn(window, "confirm").mockReturnValue(false);
  fireEvent.change(screen.getByLabelText("Rol que se modificará"), { target: { value: "2" } });
  expect(screen.getByLabelText("Rol que se modificará")).toHaveValue("1");
  expect(checkbox).toBeChecked();
});
