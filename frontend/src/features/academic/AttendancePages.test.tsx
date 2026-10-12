import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { AttendanceWorkspacePage, StudentAttendancePage } from "./AttendancePages";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function setup(student = false) {
  useAuthStore.setState({ user: { user_id: student ? 3 : 1, username: "demo", email: "demo@example.com", role_id: 1, role_name: student ? "student" : "admin", student_id: student ? 1 : null, teacher_id: null }, token: "test" });
  const data = student ? [{ enrollment_id: 5, section_id: 1, section_code: "MAT-A", subject_code: "MAT", subject_name: "Matemática", period: "2026-2", state: "enrolled", present_count: 1, total_count: 2, percentage: 50, counts: { present: 1, excused: 1 }, records: [{ attendance_id: 1, date: "2026-09-21", status: "present", note: "", excuse_reference: "" }, { attendance_id: 2, date: "2026-09-23", status: "excused", note: "Certificado médico", excuse_reference: "MED-1" }] }] : { section_id: 1, section_code: "MAT-A", subject_name: "Matemática", teacher_name: "Ana Pérez", period_name: "2026-2", days_of_week: "Lunes, Miércoles", roster: [
    { enrollment_id: 5, name: "Luis Demo", enrollment_number: "EST-5", state: "enrolled", attendance_id: null, status: null, note: "", excuse_reference: "" },
    { enrollment_id: 6, name: "Eva Demo", enrollment_number: "EST-6", state: "enrolled", attendance_id: 2, status: "present", note: "", excuse_reference: "" },
  ] };
  vi.spyOn(api, "get").mockResolvedValue({ data } as never);
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: [] } as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[student ? "/my-attendance" : "/sections/1"]}><Routes><Route path="/sections/:sectionId" element={<AttendanceWorkspacePage />} /><Route path="/my-attendance" element={<StudentAttendancePage />} /></Routes></MemoryRouter></QueryClientProvider>);
  return post;
}

it("does not premark missing attendance and saves only changed students", async () => {
  const post = setup();
  expect(await screen.findByLabelText("Estado de Luis Demo")).toHaveValue("");
  expect(screen.getByLabelText("Estado de Eva Demo")).toHaveValue("present");
  expect(screen.getByRole("button", { name: "Guardar asistencia" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Estado de Luis Demo"), { target: { value: "absent" } });
  fireEvent.change(screen.getByLabelText("Motivo del registro o corrección"), { target: { value: "Pase de lista" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar asistencia" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/attendances/bulk", expect.objectContaining({ section_id: 1, reason: "Pase de lista", records: [{ enrollment_id: 5, status: "absent", note: "", excuse_reference: "" }] })));
});

it("requires a justification and preserves unsaved changes when date change is refused", async () => {
  setup();
  await screen.findByLabelText("Estado de Luis Demo");
  fireEvent.change(screen.getByLabelText("Estado de Luis Demo"), { target: { value: "excused" } });
  fireEvent.change(screen.getByLabelText("Motivo del registro o corrección"), { target: { value: "Justificante recibido" } });
  expect(screen.getByRole("button", { name: "Guardar asistencia" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Observación de Luis Demo"), { target: { value: "Certificado" } });
  expect(screen.getByRole("button", { name: "Guardar asistencia" })).toBeEnabled();
  vi.spyOn(window, "confirm").mockReturnValue(false);
  fireEvent.change(screen.getByLabelText("Fecha de clase"), { target: { value: "2026-09-21" } });
  expect(screen.getByLabelText("Estado de Luis Demo")).toHaveValue("excused");
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
