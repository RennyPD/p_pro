import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { dueLabel } from "../../lib/dueLabel";
import { TaskCard } from "./TaskCard";

afterEach(cleanup);

const base = {
  title: "Actividad práctica 1",
  instructions: "Desarrolla el caso y presenta conclusiones justificadas.",
  subjectName: "Fundamentos de programación",
  sectionCode: "DS-101-A",
  teacherName: "Ana Rodríguez",
  maxScore: 100,
  graded: true,
  status: "Vencida",
  tone: "danger" as const,
};

it("describes due dates relative to now", () => {
  const now = new Date("2026-11-18T12:00:00");
  expect(dueLabel(new Date("2026-11-19T12:00:00"), now)).toBe("Vence mañana");
  expect(dueLabel(new Date("2026-11-15T12:00:00"), now)).toBe("Venció hace 3 días");
  expect(dueLabel(new Date("2026-11-18T15:00:00"), now)).toBe("Vence dentro de 3 horas");
  expect(dueLabel(new Date("2026-10-05T12:00:00"), now)).toBe("Venció hace 6 semanas");
});

it("shows a compact graded task with status tone and submissions", () => {
  render(
    <TaskCard
      task={{ ...base, dueAt: new Date(Date.now() - 86_400_000 * 3), submissionCount: 4 }}
      actions={<button type="button">Revisar entregas</button>}
    />,
  );
  expect(screen.getByRole("heading", { name: "Actividad práctica 1" })).toBeInTheDocument();
  expect(screen.getByText("Vencida").closest("article")).toHaveAttribute("data-tone", "danger");
  expect(screen.getByText("Venció hace 3 días")).toBeInTheDocument();
  expect(screen.getByText("100 pts")).toBeInTheDocument();
  expect(screen.getByText("4 entregas")).toBeInTheDocument();
  expect(screen.getByText("DS-101-A")).toBeInTheDocument();
});

it("labels practice tasks and hides the submission count for students", () => {
  render(
    <TaskCard
      task={{ ...base, graded: false, dueAt: new Date(Date.now() + 86_400_000 * 5) }}
      actions={null}
    />,
  );
  expect(screen.getByText("Práctica")).toBeInTheDocument();
  expect(screen.queryByText(/entregas?$/)).not.toBeInTheDocument();
});
