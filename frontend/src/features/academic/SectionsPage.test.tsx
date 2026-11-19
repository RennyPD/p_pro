import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { SectionsPage } from "./SectionsPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const section = {
  section_id: 5,
  code: "DS-102-A",
  subject_code: "DS-102",
  subject_name: "Lógica",
  teacher_name: "Carlos",
  room: "Aula A-202",
  capacity: 40,
  modality: "in_person",
  days_of_week: ["Martes"],
  start_time: "10:00:00",
  end_time: "11:30:00",
  period_name: "2026-2027",
  status: "active",
};
const meeting = {
  meeting_id: 9,
  section_id: 5,
  classroom_id: 2,
  classroom_name: "Aula Sur",
  day_of_week: "Martes",
  start_time: "10:00:00",
  end_time: "11:30:00",
  modality: "in_person",
  virtual_url: "",
};
const availability = [
  {
    classroom_id: 1,
    name: "Aula Norte",
    capacity: 40,
    location: "",
    active: true,
    status: "available",
    detail: "",
  },
  {
    classroom_id: 2,
    name: "Aula Sur",
    capacity: 40,
    location: "",
    active: true,
    status: "busy",
    detail: "Ocupada por AC-102-A el Martes 10:00–11:30",
  },
];

it("shows classroom availability in the block form and blocks a busy room", async () => {
  useAuthStore.setState({
    user: {
      user_id: 1,
      username: "admin",
      email: "admin@example.com",
      role_id: 1,
      role_name: "admin",
      student_id: null,
      teacher_id: null,
    },
  });
  vi.spyOn(api, "get").mockImplementation(async path => {
    const url = String(path);
    const data = url.includes("/availability")
      ? availability
      : url.includes("/meetings")
        ? [meeting]
        : url.startsWith("/sections")
          ? [section]
          : [];
    return { data, headers: {} } as never;
  });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <SectionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Ver bloques de DS-102-A" }));
  fireEvent.click(await screen.findByRole("button", { name: "Editar bloque del Martes" }));
  const dialog = screen.getByRole("dialog");
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("Ocupada por AC-102-A");
  expect(within(dialog).getByRole("button", { name: "Guardar bloque" })).toBeDisabled();
  expect(
    within(dialog).getByRole("option", { name: /Aula Norte .*Disponible/ }),
  ).not.toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("Aula del bloque"), { target: { value: "1" } });
  expect(within(dialog).getByText("Disponible en ese horario")).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Guardar bloque" })).toBeEnabled();
});
