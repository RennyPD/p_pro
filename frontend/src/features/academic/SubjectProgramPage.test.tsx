import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { SubjectProgramPage } from "./SubjectProgramPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/subjects/7"]}>
    <Routes><Route path="/subjects/:subjectId" element={<SubjectProgramPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

describe("SubjectProgramPage", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });
  it("distinguishes the shared subject, its career plan and teaching sections", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: {
      subject: { subject_id: 7, code: "MAT-101", description: "Matemática" },
      programs: [{ curriculum_course_id: 1, career_id: 2, career_name: "Ingeniería", career_code: "ING",
        term_type: "semester", term_number: 2, credits: 4.5, course_type: "required",
        curriculum_version: "2026", is_current_version: true, prerequisite_code: null, corequisite_code: null }],
      sections: [{ section_id: 3, code: "MAT-A", teacher_name: "Ana Pérez", period_name: "2026-2",
        room: "Aula 1", capacity: 30, status: "published" }],
    } } as never);
    renderPage();
    expect(await screen.findByRole("heading", { name: "Matemática" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ingeniería" })).toHaveAttribute("href", "/careers/2");
    expect(screen.getByText("Semestre 2")).toBeInTheDocument();
    expect(screen.getByText("4.5 cr. · Obligatoria")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Secciones (1)" }));
    expect(screen.getByText("Ana Pérez")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir sección →" })).toHaveAttribute("href", "/sections/3");
  });
  it("allows catalog subjects without a career or a section", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: {
      subject: { subject_id: 7, code: "LIB-101", description: "Materia nueva" }, programs: [], sections: [],
    } } as never);
    renderPage();
    expect(await screen.findByText("Aún no pertenece a una carrera")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Incorporar a una carrera" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Secciones (0)" }));
    expect(screen.getByText("Todavía no tiene secciones")).toBeInTheDocument();
  });
});
