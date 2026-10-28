import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { CourseCatalogPage } from "./CourseCatalogPage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function prepare(cart = false) {
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: String(path).endsWith("/summary") ? { period: "2026-3", maximum_credits: 24 } : String(path).endsWith("/cart") ? (cart ? [{ cart_item_id: 1, section_id: 3, subject_name: "Matemática", subject_code: "MAT", section_code: "A", credits: 3, available_seats: 1 }] : []) : [{ section_id: 3, subject_code: "MAT", subject_name: "Matemática", section_code: "A", credits: 3, available_seats: 0, selection_status: cart ? "cart" : "enrolled", days_of_week: ["Lunes"], start_time: "08:00", end_time: "10:00", selectable: false }] } as never));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><CourseCatalogPage /></QueryClientProvider>);
}
it("does not label a student's reserved place as waitlisted when the section is full", async () => {
  prepare();
  expect(await screen.findByText("Tu plaza está reservada")).toBeInTheDocument();
  expect(screen.getByText("Confirmada")).toBeInTheDocument();
  expect(screen.queryByText("Sin cupos para nuevas selecciones")).not.toBeInTheDocument();
});
it("uses an accessible confirmation and retains per-section errors", async () => {
  vi.spyOn(api, "post").mockResolvedValue({ data: { confirmed: [], errors: [{ section_id: 3, detail: "Registration is closed" }] } });
  const native = vi.spyOn(window, "confirm");
  prepare(true);
  fireEvent.click(await screen.findByRole("button", { name: "Confirmar selección" }));
  expect(screen.getByRole("dialog", { name: "Confirmar selección académica" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Registration is closed");
  expect(native).not.toHaveBeenCalled();
});
