import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { AttendanceWorkspacePage, StudentAttendancePage } from "./AttendancePages";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const labelOf: Record<string, string> = { "": "", present: "Presente", absent: "Ausente", late: "Tardanza", excused: "Justificada" };
/** Status chosen in a student's radio group ("" when nothing is registered). */
const statusOf = (group: HTMLElement) => within(group).queryByRole("radio", { checked: true })?.textContent ?? "";
const group = (name: string) => screen.getByRole("radiogroup", { name: `Estado de ${name}` });
const choose = (name: string, status: string) => fireEvent.click(within(group(name)).getByRole("radio", { name: labelOf[status] }));

function setup(student = false, duplicate = false) {
  useAuthStore.setState({ user: { user_id: student ? 3 : 1, username: "demo", email: "demo@example.com", role_id: 1, role_name: student ? "student" : "admin", student_id: student ? 1 : null, teacher_id: null }, token: "test" });
  const data = student ? [{ enrollment_id: 5, section_id: 1, section_code: "MAT-A", subject_code: "MAT", subject_name: "Matemática", period: "2026-2", state: "enrolled", present_count: 1, total_count: 2, percentage: 50, counts: { present: 1, excused: 1 }, records: [{ attendance_id: 1, date: "2026-09-21", status: "present", note: "", excuse_reference: "" }, { attendance_id: 2, date: "2026-09-23", status: "excused", note: "Certificado médico", excuse_reference: "MED-1" }] }] : { section_id: 1, section_code: "MAT-A", subject_name: "Matemática", teacher_name: "Ana Pérez", period_name: "2026-2", days_of_week: "Lunes, Miércoles", roster: [
    { enrollment_id: 5, name: "Luis Demo", enrollment_number: "EST-5", state: "enrolled", attendance_id: null, status: null, note: "", excuse_reference: "" },
    { enrollment_id: 6, name: duplicate ? "Luis Demo" : "Eva Demo", enrollment_number: "EST-6", state: "enrolled", attendance_id: 2, status: "present", note: "", excuse_reference: "" },
  ] };
  vi.spyOn(api, "get").mockResolvedValue({ data } as never);
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: [] } as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[student ? "/my-attendance" : "/sections/1"]}><Routes><Route path="/sections/:sectionId" element={<AttendanceWorkspacePage />} /><Route path="/my-attendance" element={<StudentAttendancePage />} /></Routes></MemoryRouter></QueryClientProvider>);
  return post;
}

it("does not premark missing attendance and saves only changed students", async () => {
  const post = setup();
  expect(statusOf(await screen.findByRole("radiogroup", { name: "Estado de Luis Demo · EST-5" }))).toBe(labelOf[""]);
  expect(statusOf(group("Eva Demo · EST-6"))).toBe(labelOf["present"]);
  expect(screen.getByRole("button", { name: "Guardar asistencia" })).toBeDisabled();
  choose("Luis Demo · EST-5", "absent");
  fireEvent.change(screen.getByLabelText("Motivo del registro o corrección"), { target: { value: "Pase de lista" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar asistencia" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/attendances/bulk", expect.objectContaining({ section_id: 1, reason: "Pase de lista", records: [{ enrollment_id: 5, status: "absent", note: "", excuse_reference: "" }] })));
});

it("requires a justification and preserves unsaved changes when date change is refused", async () => {
  setup();
  await screen.findByRole("radiogroup", { name: "Estado de Luis Demo · EST-5" });
  choose("Luis Demo · EST-5", "excused");
  fireEvent.change(screen.getByLabelText("Motivo del registro o corrección"), { target: { value: "Justificante recibido" } });
  expect(screen.getByRole("button", { name: "Guardar asistencia" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Observación de Luis Demo · EST-5"), { target: { value: "Certificado" } });
  expect(screen.getByRole("button", { name: "Guardar asistencia" })).toBeEnabled();
  vi.spyOn(window, "confirm").mockReturnValue(false);
  fireEvent.change(screen.getByLabelText("Fecha de clase"), { target: { value: "21092026" } });
  expect(statusOf(group("Luis Demo · EST-5"))).toBe(labelOf["excused"]);
});

it("explains student percentages and shows dated justification details", async () => {
  setup(true);
  expect(await screen.findByText("Matemática")).toBeInTheDocument();
  expect(screen.getByText("50%")).toBeInTheDocument();
  expect(screen.getByText("1 presencias computables de 2 clases registradas en el rango.")).toBeInTheDocument();
  expect(screen.getByText(/Certificado médico · Referencia: MED-1/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Detalle de estados"), { target: { value: "late" } });
  expect(screen.getByText("No hay registros para este filtro. No significa ausencia.")).toBeInTheDocument();
});

it("distinguishes attendance controls for students sharing the same name", async () => {
  setup(false, true);
  expect(statusOf(await screen.findByRole("radiogroup", { name: "Estado de Luis Demo · EST-5" }))).toBe(labelOf[""]);
  expect(statusOf(group("Luis Demo · EST-6"))).toBe(labelOf["present"]);
});

it("shows the filtered and full attendance scope before adding changes", async () => {
  setup();
  await screen.findByRole("radiogroup", { name: "Estado de Luis Demo · EST-5" });
  fireEvent.change(screen.getByPlaceholderText("Nombre o matrícula"), { target: { value: "Eva" } });
  fireEvent.click(screen.getByRole("button", { name: "Marcar sin registrar como presentes" }));
  expect(screen.getByRole("radio", { name: "Solo visibles (0)" })).toBeChecked();
  expect(screen.getByRole("button", { name: "Marcar 0 como presentes" })).toBeDisabled();
  fireEvent.click(screen.getByRole("radio", { name: "Todo el grupo (1)" }));
  fireEvent.click(screen.getByRole("button", { name: "Marcar 1 como presentes" }));
  fireEvent.change(screen.getByPlaceholderText("Nombre o matrícula"), { target: { value: "" } });
  expect(statusOf(group("Luis Demo · EST-5"))).toBe(labelOf["present"]);
});
