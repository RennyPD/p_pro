import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { LookupSelect } from "./LookupSelect";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const config = { endpoint: "/subjects/", valueKey: "id", labelKeys: ["name"], secondaryKey: "code" };
function renderSelect(value?: number) {
  const change = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <span id="subject-label">Asignatura</span>
      <LookupSelect config={config} labelId="subject-label" value={value} onChange={change} />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Asignatura/ }));
  return change;
}

it("shows totals and navigation instead of silently truncating at eight", async () => {
  vi.spyOn(api, "get").mockResolvedValue({
    data: Array.from({ length: 19 }, (_, id) => ({ id, name: `Asignatura ${id}` })),
  });
  const change = renderSelect();
  expect(await screen.findByText("Mostrando 1–8 de 19 opciones")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Opciones siguientes" }));
  expect(screen.getByText("Mostrando 9–16 de 19 opciones")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Asignatura 12" }));
  expect(change).toHaveBeenCalledWith(12);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("searches beyond the first hundred with accents and secondary codes", async () => {
  const records = Array.from({ length: 125 }, (_, id) => ({
    id,
    name: id === 124 ? "Álgebra avanzada" : `Asignatura ${id}`,
    code: `MAT-${id}`,
  }));
  vi.spyOn(api, "get").mockImplementation(async (_path, options) => {
    const { skip } = options?.params as { skip: number };
    return { data: records.slice(skip, skip + 100) };
  });
  renderSelect();
  await screen.findByText("Mostrando 1–8 de 125 opciones");
  const search = screen.getByRole("searchbox", { name: "Buscar opciones" });
  fireEvent.change(search, { target: { value: "algebra" } });
  expect(screen.getByText("Álgebra avanzada")).toBeInTheDocument();
  expect(screen.getByText("Mostrando 1–1 de 1 opciones · 125 en total")).toBeInTheDocument();
  fireEvent.change(search, { target: { value: "MAT-124" } });
  expect(screen.getByText("Álgebra avanzada")).toBeInTheDocument();
  fireEvent.change(search, { target: { value: "no existe" } });
  expect(screen.getByText("Sin coincidencias · 125 opciones en total")).toBeInTheDocument();
});

it("opens on the selected page and supports keyboard navigation and Escape", async () => {
  vi.spyOn(api, "get").mockResolvedValue({
    data: Array.from({ length: 19 }, (_, id) => ({ id, name: `Asignatura ${id}` })),
  });
  renderSelect(18);
  await screen.findByText("Mostrando 1–8 de 19 opciones");
  fireEvent.keyDown(screen.getByRole("searchbox"), { key: "Escape" });
  const trigger = screen.getByRole("button", { name: "Asignatura Asignatura 18" });
  expect(trigger).toHaveFocus();
  fireEvent.click(trigger);
  expect(screen.getByText("Mostrando 17–19 de 19 opciones")).toBeInTheDocument();
  fireEvent.keyDown(screen.getByRole("searchbox"), { key: "ArrowDown" });
  expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Asignatura 16" })).toHaveFocus();
});

it("shows an explicit retry state and can clear an optional selection", async () => {
  vi.spyOn(api, "get").mockRejectedValue(new Error("offline"));
  const change = renderSelect(7);
  expect(await screen.findByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  expect(screen.getByText(/no disponible en este catálogo/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Limpiar selección" }));
  expect(change).toHaveBeenCalledWith(null);
});

it("keeps the menu and selection when paging to a single final option and back", async () => {
  vi.spyOn(api, "get").mockResolvedValue({
    data: Array.from({ length: 17 }, (_, id) => ({ id, name: `Asignatura ${id}` })),
  });
  const change = renderSelect(3);
  await screen.findByText("Mostrando 1–8 de 17 opciones");
  const next = screen.getByRole("button", { name: "Opciones siguientes" });
  next.focus();
  fireEvent.click(next);
  next.focus();
  fireEvent.click(next);
  const pagination = screen.getByRole("navigation", { name: "Páginas de opciones" });
  expect(pagination).toHaveFocus();
  expect(next).toBeDisabled();
  expect(screen.getByText("Mostrando 17–17 de 17 opciones")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Asignatura Asignatura 3" })).toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
  const previous = screen.getByRole("button", { name: "Opciones anteriores" });
  previous.focus();
  fireEvent.click(previous);
  previous.focus();
  fireEvent.click(previous);
  expect(previous).toBeDisabled();
  expect(pagination).toHaveFocus();
  expect(screen.getByText("Mostrando 1–8 de 17 opciones")).toBeInTheDocument();
  fireEvent.click(next);
  fireEvent.click(next);
  fireEvent.click(screen.getByRole("button", { name: "Asignatura 16" }));
  expect(change).toHaveBeenCalledExactlyOnceWith(16);
});
