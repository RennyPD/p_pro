import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { GuardianPortalPage } from "./GuardianPortalPage";

const ALL = { academic: true, attendance: true, finance: true, tasks: true };

function student(overrides: Record<string, unknown> = {}) {
  return {
    student_id: 1,
    student_name: "Sofía García",
    enrollment_number: "ITH-2026-001",
    career_name: "Desarrollo de Software",
    active: true,
    permissions: ALL,
    average_grade: 88.5,
    final_grade_count: 2,
    provisional_average_grade: null,
    provisional_grade_count: 0,
    attendance_percentage: 94,
    attendance_count: 18,
    metrics_period: "2026-2027",
    balance: 1250,
    schedule: [],
    alerts: [],
    ...overrides,
  };
}

function mockApi(overview: unknown[], details: Record<string, unknown> = {}) {
  return vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url === "/operations/guardian/overview") return Promise.resolve({ data: overview });
    const area = url.split("/").at(-1) ?? "";
    if (area in details)
      return Promise.resolve({ data: details[area], headers: { "x-total-count": "1" } });
    return Promise.resolve({ data: new Blob() });
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <GuardianPortalPage />
    </QueryClientProvider>,
  );
}

describe("GuardianPortalPage", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("summarizes grades, attendance, balance and alerts of the linked student", async () => {
    mockApi([student()]);
    renderPage();
    expect(await screen.findByText("Sofía García")).toBeInTheDocument();
    const metrics = screen.getByRole("region", { name: "Indicadores principales" });
    expect(within(metrics).getByText("88.5")).toBeInTheDocument();
    expect(within(metrics).getByText("94%")).toBeInTheDocument();
    expect(within(metrics).getByText(/1,250/)).toBeInTheDocument();
    const tabs = screen.getByRole("tablist", { name: "Información del estudiante" });
    expect(
      within(tabs)
        .getAllByRole("tab")
        .map(tab => tab.textContent),
    ).toEqual(["Resumen", "Asistencia", "Notas", "Tareas", "Pagos", "Desempeño"]);
  });

  it("hides the areas the institution restricted for this link", async () => {
    mockApi([student({ permissions: { ...ALL, finance: false, tasks: false }, balance: null })]);
    renderPage();
    const tabs = await screen.findByRole("tablist", { name: "Información del estudiante" });
    expect(within(tabs).queryByRole("tab", { name: "Pagos" })).not.toBeInTheDocument();
    expect(within(tabs).queryByRole("tab", { name: "Tareas" })).not.toBeInTheDocument();
    expect(screen.queryByText("Balance")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Documentos"));
    expect(screen.queryByRole("button", { name: /Estado de cuenta/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Boletín/ })).toBeInTheDocument();
  });

  it("opens the attendance detail by subject and day", async () => {
    const get = mockApi([student()], {
      attendance: {
        student_id: 1,
        period: "2026-2027",
        present_count: 9,
        total_count: 10,
        percentage: 90,
        counts: { present: 9, absent: 1, late: 0, excused: 0 },
        courses: [
          {
            section_id: 3,
            section_code: "DS-101-A",
            subject_code: "DS-101",
            subject_name: "Fundamentos de Programación",
            present_count: 9,
            total_count: 10,
            percentage: 90,
            enrollment_id: 5,
            records: [
              {
                attendance_id: 1,
                date: "2026-09-11",
                status: "absent",
                note: "",
                excuse_reference: "",
              },
            ],
          },
        ],
      },
    });
    renderPage();
    fireEvent.click(await screen.findByRole("tab", { name: "Asistencia" }));
    expect(await screen.findByText("Fundamentos de Programación")).toBeInTheDocument();
    const days = screen.getByRole("list", { name: "Días de Fundamentos de Programación" });
    expect(within(days).getByText("Ausente")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/guardian/students/1/attendance", { params: undefined });
  });

  it("switches between linked children", async () => {
    mockApi([
      student(),
      student({ student_id: 2, student_name: "Mateo García", average_grade: 70 }),
    ]);
    renderPage();
    const children = await screen.findByRole("tablist", { name: "Estudiantes vinculados" });
    fireEvent.click(within(children).getByRole("tab", { name: /Mateo/ }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Mateo García" })).toBeInTheDocument(),
    );
    expect(screen.getByText("70")).toBeInTheDocument();
  });

  it("translates alert categories and priorities", async () => {
    mockApi([
      student({
        alerts: [
          {
            early_alert_id: 1,
            category: "academic",
            severity: "high",
            reason: "Revisar progreso",
            follow_up_date: null,
          },
        ],
      }),
    ]);
    renderPage();
    expect(await screen.findByText("Académica")).toBeInTheDocument();
    expect(screen.getByText("Prioridad Alta")).toBeInTheDocument();
    expect(screen.queryByText("academic")).not.toBeInTheDocument();
  });

  it("lets the guardian download the linked student's documents", async () => {
    const get = mockApi([student({ student_id: 7, enrollment_number: "ITH-007" })]);
    renderPage();
    fireEvent.click(await screen.findByText("Documentos"));
    fireEvent.click(screen.getByRole("button", { name: /Boletín/ }));
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/documents/students/7/report-card.pdf", {
        responseType: "blob",
      }),
    );
  });
});
