import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useForm, type FieldValues } from "react-hook-form";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { ClassroomPicker } from "./ClassroomPicker";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const rooms = [
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
    detail: "Ocupada por DS-202-A el Lunes 08:00–09:30",
  },
];

function Harness({ room, onSave }: { room: string; onSave: (values: FieldValues) => void }) {
  const { control, handleSubmit } = useForm<FieldValues>({
    defaultValues: {
      room,
      days_of_week: ["Lunes"],
      start_time: "08:00",
      end_time: "09:30",
      capacity: 30,
      period_name: "2026-2027",
      modality: "in_person",
      status: "draft",
    },
  });
  return (
    <form onSubmit={handleSubmit(onSave)}>
      <ClassroomPicker name="room" label="Aula" control={control} />
      <button type="submit">Guardar</button>
    </form>
  );
}

function renderPicker(room: string) {
  vi.spyOn(api, "get").mockResolvedValue({ data: rooms } as never);
  const onSave = vi.fn();
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Harness room={room} onSave={onSave} />
    </QueryClientProvider>,
  );
  return onSave;
}

it("lists classrooms with their availability and disables busy ones", async () => {
  renderPicker("Por asignar");
  const free = await screen.findByRole("option", { name: /Aula Norte · 40 plazas · Disponible/ });
  expect(free).not.toBeDisabled();
  expect(screen.getByRole("option", { name: /Aula Sur .*Ocupada por DS-202-A/ })).toBeDisabled();
  expect(api.get).toHaveBeenCalledWith(
    "/scheduling/classrooms/availability",
    expect.objectContaining({
      params: expect.objectContaining({ days: "Lunes", start_time: "08:00" }),
    }),
  );
});

it("warns about a busy classroom and does not let the form save", async () => {
  const onSave = renderPicker("Aula Sur");
  expect(await screen.findByRole("alert")).toHaveTextContent("Ocupada por DS-202-A");
  fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Aula Sur"));
  expect(onSave).not.toHaveBeenCalled();
});

it("saves when the chosen classroom is free", async () => {
  const onSave = renderPicker("Por asignar");
  await screen.findByRole("option", { name: /Aula Norte/ });
  fireEvent.change(screen.getByLabelText("Aula"), { target: { value: "Aula Norte" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(onSave).toHaveBeenCalled());
  expect(onSave.mock.calls[0][0].room).toBe("Aula Norte");
});
