import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { ClassGroupPage } from "./ClassGroupPage";

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
      left_on: null,
      result: "pending",
      result_confirmed_at: null,
      result_note: null,
      financial_hold: false,
      academic_hold: false,
    },
  ],
  subjects: [
    {
      subject_id: 3,
      code: "MAT1",
      name: "Matemática 1",
      teacher_id: 1,
      teacher_name: "Laura Gómez",
      sections: 0,
    },
  ],
  open_periods: ["Período 1 · 2026-2027"],
};

const promotion = {
  class_group_id: 7,
  passing_grade: 70,
  periods: ["Período 1"],
  members: [
    {
      member_id: 11,
      student_id: 5,
      student_name: "Ana Díaz",
      enrollment_number: "ESC-005",
      subjects: [
        {
          subject_id: 3,
          code: "MAT1",
          name: "Matemática 1",
          periods: [62],
          average: 62,
          complete: true,
          passed: false,
        },
      ],
      failed: ["MAT1"],
      complete: true,
      proposal: "completivo",
      result: "pending",
      confirmed: false,
    },
  ],
};

function mockGet() {
  return vi.spyOn(api, "get").mockImplementation(url => {
    if (url === "/class-groups/7") return Promise.resolve({ data: group });
    if (url === "/class-groups/7/promotion") return Promise.resolve({ data: promotion });
    return Promise.resolve({ data: [] });
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/class-groups/7"]}>
        <Routes>
          <Route path="/class-groups/:groupId" element={<ClassGroupPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ClassGroupPage", () => {
  it("shows members and generates the subjects of the grade", async () => {
    mockGet();
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { sections_created: 4, enrollments_created: 4 } });
    renderPage();
    expect(await screen.findByRole("heading", { name: "1.º A" })).toBeInTheDocument();
    expect(screen.getByText("Ana Díaz")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Materias/ }));
    expect(screen.getByText("Sin generar")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Generar materias/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/class-groups/7/generate-subjects"));
  });

  it("confirms the proposed result of a student", async () => {
    mockGet();
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: promotion });
    renderPage();
    await userEvent.click(await screen.findByRole("tab", { name: /Promoción/ }));
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Completivo", { selector: ".vs-chip" })).toBeInTheDocument();
    expect(within(table).getByText("62")).toHaveClass("is-low");
    const confirm = screen.getByRole("button", { name: /Confirmar resultados/ });
    expect(confirm).toBeDisabled();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resultado de Ana Díaz" }),
      "repeated",
    );
    await userEvent.click(confirm);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/class-groups/7/promotion", {
        decisions: [{ member_id: 11, result: "repeated" }],
      }),
    );
  });
});
