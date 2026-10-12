import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { OperationsPage } from "./OperationsPage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const task = { assignment_id: 1, section_id: 2, title: "Proyecto de algoritmos", instructions: "Explica tu solución paso a paso", due_at: "2099-01-01T23:00:00", max_score: 20, assessment_id: null, published: true, lifecycle: "open", allow_late: false, allow_resubmit: true, subject_name: "Programación", section_code: "PROG-A", teacher_name: "Ana Pérez", period_name: "2026-2", submission: null, submission_count: 0 };
function setup(role: "admin" | "student", submission = null as null | { submission_id: number; content: string; submitted_at: string; score: number; feedback: string; status: string; attempts: number }) {
  useAuthStore.setState({ user: { user_id: role === "admin" ? 1 : 3, username: role, email: `${role}@example.com`, role_id: 1, role_name: role, student_id: role === "student" ? 1 : null, teacher_id: null }, token: "test" });
  const get = vi.spyOn(api, "get").mockImplementation(async path => ({ data: path === "/operations/assignments" ? [{ ...task, submission }] : path === "/operations/task-sections" ? [{ section_id: 2, code: "PROG-A", subject_name: "Programación", period_name: "2026-2" }] : path.includes("/submissions") ? [{ student_id: 1, student_name: "Luis Demo", enrollment_number: "EST-001", submission }] : [] } as never));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><OperationsPage /></MemoryRouter></QueryClientProvider>);
  return get;
}

it("shows readable subject context and records a student delivery", async () => {
  const get = setup("student");
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
  expect(await screen.findByText("Proyecto de algoritmos")).toBeInTheDocument();
  expect(screen.queryByText("Crear tarea")).not.toBeInTheDocument();
  expect(screen.getByText(/Práctica: no afecta/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Ver tarea"));
  fireEvent.change(screen.getByLabelText("Contenido de la entrega"), { target: { value: "Mi solución" } });
  fireEvent.click(screen.getByText("Entregar tarea"));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/operations/assignments/1/submit", { content: "Mi solución" }));
  expect(get).not.toHaveBeenCalledWith("/operations/alerts");
});

it("preserves a graded zero and prevents resubmission", async () => {
  setup("student", { submission_id: 4, content: "Intento inicial", submitted_at: "2026-10-10T12:00:00", score: 0, feedback: "Revisa los fundamentos", status: "graded", attempts: 1 });
  fireEvent.click(await screen.findByText("Ver tarea"));
  expect(screen.getByText("0/20")).toBeInTheDocument();
  expect(screen.getByText(/Revisa los fundamentos/)).toBeInTheDocument();
  expect(screen.queryByText("Reenviar")).not.toBeInTheDocument();
});

it("creates task drafts with editable instructions and policies", async () => {
  setup("admin");
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
  fireEvent.click(await screen.findByText("Crear tarea"));
  fireEvent.change(screen.getByLabelText("Asignatura y sección"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Investigación" } });
  fireEvent.change(screen.getByLabelText("Instrucciones"), { target: { value: "Investiga y explica" } });
  fireEvent.change(screen.getByLabelText("Fecha y hora límite"), { target: { value: "2099-01-01T18:00" } });
  fireEvent.change(screen.getByLabelText("Puntuación máxima"), { target: { value: "30" } });
  fireEvent.click(screen.getByText("Guardar tarea"));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/operations/assignments", expect.objectContaining({ published: false, instructions: "Investiga y explica", max_score: 30, section_id: 2, allow_late: false })));
});

it("switches the agenda between month, week and list with configurable time", async () => {
  setup("student");
  await screen.findByText("Proyecto de algoritmos");
  fireEvent.click(screen.getByRole("tab", { name: "Agenda académica" }));
  expect(document.querySelectorAll(".agenda-day")).toHaveLength(42);
  fireEvent.change(screen.getByLabelText("Vista"), { target: { value: "week" } });
  expect(document.querySelectorAll(".agenda-day")).toHaveLength(7);
  fireEvent.change(screen.getByLabelText("Hora"), { target: { value: "12" } });
  expect(screen.getByLabelText("Hora")).toHaveValue("12");
  fireEvent.change(screen.getByLabelText("Vista"), { target: { value: "list" } });
  expect(document.querySelectorAll(".agenda-day")).toHaveLength(0);
});
