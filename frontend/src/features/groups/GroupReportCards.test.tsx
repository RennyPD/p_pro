import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { GroupReportCardsTab } from "./GroupReportCardsTab";
import type { ClassGroupDetail } from "./groupsData";

vi.mock("../../lib/permissions", () => ({
  useAccess: () => ({ can: () => true }),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const group = {
  class_group_id: 7,
  career_id: 2,
  grade_number: 1,
  name: "A",
  school_year_id: 1,
  homeroom_teacher_id: 1,
  room: "Aula 3",
  capacity: 30,
  status: "active",
  label: "1.º A · Secundaria",
  career_name: "Secundaria",
  school_year_name: "2026-2027",
  homeroom_teacher_name: "Laura Gómez",
  member_count: 1,
  members: [
    {
      member_id: 11,
      student_id: 5,
      student_name: "Ana Díaz",
      enrollment_number: "ESC-005",
      status: "enrolled",
      joined_on: "2026-08-17",
      result: "pending",
    },
  ],
  subjects: [],
  open_periods: [],
} as unknown as ClassGroupDetail;

const card = {
  student_id: 5,
  student_name: "Ana Díaz",
  enrollment_number: "ESC-005",
  member_id: 11,
  member_status: "enrolled",
  institution: {
    name: "Colegio Horizonte",
    school_code: "12345",
    regional: "10",
    district: "10-03",
  },
  class_group_id: 7,
  group_label: "1.º A · Secundaria",
  career_name: "Secundaria",
  grade_number: 1,
  school_year: "2026-2027",
  homeroom_teacher: "Laura Gómez",
  scale_name: "Numérica 0–100",
  passing_grade: 70,
  periods: [
    { period_id: 1, name: "Período 1 · 2026-2027", short: "P1", closed: true },
    { period_id: 2, name: "Período 2 · 2026-2027", short: "P2", closed: false },
  ],
  subjects: [
    {
      subject_id: 3,
      code: "MAT1",
      name: "Matemática 1",
      periods: ["88", null],
      average: 88,
      average_label: "88",
      completivo: null,
      extraordinario: null,
      final: null,
      status: "incomplete",
      status_label: "En curso",
    },
  ],
  attendance: [
    {
      period: "Período 1 · 2026-2027",
      present: 18,
      late: 1,
      absent: 1,
      excused: 0,
      total: 20,
      percentage: 95,
    },
  ],
  comments: [],
  result: "pending",
  result_label: "Pendiente",
};

describe("GroupReportCardsTab", () => {
  it("shows the report card with running periods and saves a remark", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: card });
    const put = vi.spyOn(api, "put").mockResolvedValue({
      data: {
        ...card,
        comments: [{ period_id: 1, period: "Período 1 · 2026-2027", comment: "Excelente" }],
      },
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <GroupReportCardsTab group={group} />
      </QueryClientProvider>,
    );
    const article = await screen.findByRole("article", { name: "Boletín de Ana Díaz" });
    expect(within(article).getByText(/Código 12345/)).toBeInTheDocument();
    const row = within(article).getByRole("row", { name: /Matemática 1/ });
    expect(within(row).getAllByText("88")).toHaveLength(2);
    expect(within(row).getAllByText("En curso").length).toBeGreaterThan(0);
    expect(within(article).getByText("95 %")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Observación para Ana Díaz"), "Excelente");
    await userEvent.click(screen.getByRole("button", { name: "Guardar observación" }));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith("/class-groups/7/members/11/comments/1", {
        comment: "Excelente",
      }),
    );
    const remarks = await screen.findByRole("region", { name: "Observaciones del titular" });
    expect(within(remarks).getByText(/Excelente/)).toBeInTheDocument();
  });

  it("shows the competency groups of the official secondary card", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: {
        ...card,
        format: "minerd_secondary",
        competency_groups: ["Comunicativa", "Pensamiento", "Científica", "Ética"],
        subjects: [
          {
            ...card.subjects[0],
            especial: "75",
            competencies: [
              ["80", null],
              ["90", null],
              ["70", null],
              ["100", null],
            ],
          },
        ],
      },
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <GroupReportCardsTab group={group} />
      </QueryClientProvider>,
    );
    const table = await screen.findByRole("table", {
      name: "Calificaciones por competencias fundamentales",
    });
    expect(within(table).getByRole("columnheader", { name: "Comunicativa" })).toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /Matemática 1/ });
    expect(within(row).getByText("100")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Especial" })).toBeInTheDocument();
  });
});
